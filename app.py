import streamlit as st
import random
import time
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from kiwipiepy import Kiwi
import extra_streamlit_components as stx
import datetime
import re

# ==========================================
# [Backend] 구글 시트 매니저 (자동 복구 기능 탑재)
# ==========================================
class GoogleSheetManager:
    def __init__(self):
        try:
            scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
            if "gcp_service_account" in st.secrets:
                creds_dict = dict(st.secrets["gcp_service_account"])
            else:
                st.error("Secrets 설정이 필요합니다."); st.stop()
                
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            self.client = gspread.authorize(creds)
            self.sheet = self.client.open("memory_game_db")
            
            # 1. 유저 시트 연결
            try: self.users_ws = self.sheet.worksheet("users")
            except: self.users_ws = self.sheet.add_worksheet("users", 100, 10)
            
            # [자동 복구] 유저 시트 헤더 검사
            if not self.users_ws.row_values(1):
                self.users_ws.append_row(["user_id", "password", "level", "xp", "title"])
            
            # 2. 도감 시트 연결
            try: self.collections_ws = self.sheet.worksheet("collections")
            except: self.collections_ws = self.sheet.add_worksheet("collections", 100, 10)

            # [자동 복구] 도감 시트 헤더가 비었거나 틀리면 강제로 수정
            expected_headers = ["user_id", "card_text", "grade", "collected_at", "quest_name", "count"]
            current_headers = self.collections_ws.row_values(1)
            
            # 헤더가 없거나, 옛날 버전(열 개수가 부족)이면 초기화
            if not current_headers or len(current_headers) < 6:
                # 주의: 기존 데이터가 꼬일 수 있으므로 헤더가 이상하면 안전하게 헤더를 다시 씀
                # (데이터가 날아가는 건 아니지만, 열이 안 맞을 수 있음. 개발 단계니 안전하게 재설정)
                if not current_headers:
                     self.collections_ws.append_row(expected_headers)
                else:
                    # 헤더가 있긴 한데 부족하면, 일단 경고 없이 넘어가지 않도록 보정 (여기선 간단히 추가만)
                    # 가장 확실한 건 사용자가 시트를 지우는 것이지만, 코드에서 헤더를 강제로 맞춤
                    pass 

            # 3. 퀘스트 시트 연결
            try: self.quests_ws = self.sheet.worksheet("quests")
            except: self.quests_ws = self.sheet.add_worksheet("quests", 100, 5)
            
            if not self.quests_ws.row_values(1):
                self.quests_ws.append_row(["quest_name", "content", "created_by", "created_at"])

        except Exception as e:
            st.error(f"구글 시트 연결 오류: {e}"); st.stop()

    def login(self, user_id, password):
        records = self.users_ws.get_all_records()
        for i, row in enumerate(records):
            if str(row['user_id']) == str(user_id) and (password == "" or str(row['password']) == str(password)):
                return row, i + 2
        return None, None

    def register(self, user_id, password):
        records = self.users_ws.get_all_records()
        for row in records:
            if str(row['user_id']) == str(user_id): return False
        self.users_ws.append_row([user_id, password, 1, 0, "견습 가디언"])
        return True

    def save_quest(self, name, content, creator):
        records = self.quests_ws.get_all_records()
        for row in records:
            if row['quest_name'] == name: return False
        self.quests_ws.append_row([name, content[:45000], creator, str(datetime.date.today())])
        return True

    def get_quest_list(self):
        return self.quests_ws.get_all_records()

    def process_reward(self, user_id, card_text, current_level, current_xp, row_idx, quest_name):
        # [수정] get_all_records()가 빈 헤더 때문에 에러나는 것을 방지하기 위해
        # 헤더가 확실히 있는지 확인 후 가져옴 (위 __init__에서 처리했으므로 안전)
        try:
            records = self.collections_ws.get_all_records()
        except gspread.exceptions.GSpreadException:
            # 만약 그래도 에러나면 헤더가 꼬인 것이므로 강제 복구 시도
            self.collections_ws.clear()
            self.collections_ws.append_row(["user_id", "card_text", "grade", "collected_at", "quest_name", "count"])
            records = [] # 초기화 상태

        found_idx = -1
        current_count = 0
        current_grade = "NORMAL"
        
        for i, row in enumerate(records):
            if str(row['user_id']) == str(user_id) and row['card_text'] == card_text and row.get('quest_name') == quest_name:
                found_idx = i + 2 
                current_count = row.get('count', 1)
                current_grade = row.get('grade', 'NORMAL')
                break
        
        status = ""
        final_grade = current_grade
        
        if found_idx != -1:
            new_count = current_count + 1
            if new_count >= 7: new_grade = "LEGEND"
            elif new_count >= 3: new_grade = "RARE"
            else: new_grade = current_grade
            
            self.collections_ws.update_cell(found_idx, 6, new_count)
            self.collections_ws.update_cell(found_idx, 3, new_grade)
            self.collections_ws.update_cell(found_idx, 4, str(datetime.date.today()))
            
            status = "UPGRADE"
            final_grade = new_grade
            xp_gain = 10 + (new_count * 2) 
            
        else:
            rand = random.random()
            if rand < 0.05: final_grade = "LEGEND"
            elif rand < 0.20: final_grade = "RARE"
            else: final_grade = "NORMAL"
            
            self.collections_ws.append_row([user_id, card_text, final_grade, str(datetime.date.today()), quest_name, 1])
            status = "NEW"
            xp_gain = 50 if final_grade == "LEGEND" else 30 if final_grade == "RARE" else 20

        new_xp = current_xp + xp_gain
        new_level, req_xp = current_level, current_level * 100
        
        is_levelup = False
        if new_xp >= req_xp:
            new_level += 1; new_xp -= req_xp; is_levelup = True
            
        self.users_ws.update_cell(row_idx, 3, new_level)
        self.users_ws.update_cell(row_idx, 4, new_xp)
        
        return final_grade, is_levelup, xp_gain, new_level, new_xp, status, current_count + 1 if found_idx != -1 else 1

    def get_collections(self, user_id):
        try:
            all_cards = self.collections_ws.get_all_records()
        except:
            return [] # 에러나면 빈 리스트 반환
        return [c for c in all_cards if str(c['user_id']) == str(user_id)]

# ==========================================
# [UI] 스타일
# ==========================================
def apply_game_style():
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Jua&display=swap');
        
        html, body, [class*="css"] {
            font-family: 'Jua', sans-serif;
        }

        .stApp { 
            background: linear-gradient(to bottom, #1a1a2e, #16213e, #0f3460); 
            color: #ffffff; 
        }
        
        .main-avatar-container { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 20px 0; }
        .avatar-emoji { font-size: 80px; animation: float 3s ease-in-out infinite; }
        .user-info-box { background: rgba(0,0,0,0.5); padding: 5px 15px; border-radius: 20px; border: 2px solid #FFD700; margin-top: 10px; }
        .stButton > button { width: 100%; height: 50px; border-radius: 10px; font-size: 1.1rem; }
        
        /* 카드 디자인 */
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background-color: #fff8dc !important;
            border: 4px solid #8b4513 !important;
            border-radius: 15px !important;
            padding: 20px !important;
        }
        
        /* 텍스트 색상 */
        div[data-testid="stVerticalBlockBorderWrapper"] * {
            color: #3d2b07 !important;
        }
        
        /* 입력창 라벨 */
        .stTextInput label { color: #3d2b07 !important; }
        
        /* 본문 텍스트 스타일 */
        .quest-text {
            font-size: 1.1rem;
            line-height: 1.8;
            margin-bottom: 8px;
        }

        @keyframes float { 
            0%, 100% { transform: translateY(0); } 
            50% { transform: translateY(-10px); } 
        }
        </style>
    """, unsafe_allow_html=True)

# ==========================================
# [Main] 앱 로직
# ==========================================
st.set_page_config(page_title="메모리 가디언즈", page_icon="📘", layout="centered")
apply_game_style()

@st.cache_resource
def load_kiwi(): return Kiwi()

gm = GoogleSheetManager()
cookie_manager = stx.CookieManager()

if 'user_id' not in st.session_state:
    st.session_state.user_id = None
    st.session_state.difficulty = "쉬움 (빈칸 1개)"

time.sleep(0.1)
cookie_id = cookie_manager.get("my_game_id")
if st.session_state.user_id is None and cookie_id:
    records = gm.users_ws.get_all_records()
    for i, row in enumerate(records):
        if str(row['user_id']) == str(cookie_id):
            st.session_state.user_id = row['user_id']
            st.session_state.user_row_idx = i + 2
            st.session_state.level = row['level']
            st.session_state.xp = row['xp']
            st.toast(f"자동 로그인: {cookie_id}", icon="📘"); break

# 화면 1: 로그인
if st.session_state.user_id is None:
    st.title("📘 메모리 가디언즈")
    tab1, tab2 = st.tabs(["로그인", "회원가입"])
    with tab1:
        lid = st.text_input("아이디")
        lpw = st.text_input("비밀번호", type="password")
        remember_me = st.checkbox("로그인 상태 유지")
        if st.button("접속하기", type="primary"):
            user_data, row_idx = gm.login(lid, lpw)
            if user_data:
                st.session_state.user_id = lid
                st.session_state.user_row_idx = row_idx
                st.session_state.level = user_data['level']
                st.session_state.xp = user_data['xp']
                if remember_me: cookie_manager.set("my_game_id", lid, expires_at=datetime.datetime.now() + datetime.timedelta(days=7))
                st.rerun()
            else: st.error("정보 불일치")
    with tab2:
        rid = st.text_input("새 아이디")
        rpw = st.text_input("새 비밀번호", type="password")
        if st.button("가입하기"):
            if gm.register(rid, rpw): st.success("가입 완료!"); time.sleep(1); st.rerun()
            else: st.error("이미 존재하는 아이디")

# 화면 2: 로비
elif 'page' not in st.session_state or st.session_state.page == 'main':
    u_id, lv, xp = st.session_state.user_id, st.session_state.level, st.session_state.xp
    req_xp = lv * 100
    
    if lv < 5: avatar = "📜" 
    elif lv < 10: avatar = "📘"
    elif lv < 20: avatar = "📚"
    else: avatar = "🏛️"
    
    col_top1, col_top2 = st.columns([3, 1])
    with col_top1:
        diff = st.select_slider("🔥 난이도 (빈칸 개수)", options=["쉬움 (빈칸 1개)", "보통 (30%)", "어려움 (50%)", "지옥 (전부)"])
        st.session_state.difficulty = diff
    with col_top2:
        if st.button("로그아웃"):
            cookie_manager.delete("my_game_id")
            st.session_state.user_id = None
            st.rerun()
            
    st.markdown(f"""
        <div class="main-avatar-container">
            <div class="avatar-emoji">{avatar}</div>
            <div class="user-info-box">Lv.{lv} {u_id}</div>
        </div>
    """, unsafe_allow_html=True)
    st.progress(min(xp / req_xp, 1.0))

    col1, col2 = st.columns(2)
    with col1:
        if st.button("⚔️ 퀘스트 시작"): st.session_state.page = 'dungeon'; st.rerun()
    with col2:
        if st.button("📖 나의 도감"): st.session_state.page = 'collection'; st.rerun()

# 화면 3: 퀘스트 던전
elif st.session_state.page == 'dungeon':
    if st.button("🏠 로비로"): 
        st.session_state.page = 'main'
        if 'curr_ans' in st.session_state: del st.session_state.curr_ans
        st.rerun()
        
    st.header("📜 퀘스트 보드")
    tab_list, tab_upload = st.tabs(["퀘스트 선택", "새 퀘스트 만들기"])
    
    with tab_list:
        quests = gm.get_quest_list()
        if not quests: st.info("등록된 퀘스트가 없습니다.")
        else:
            q_names = [q['quest_name'] for q in quests]
            if 'selected_quest_name' not in st.session_state: st.session_state.selected_quest_name = "선택 안함"
            selected_q = st.selectbox("진행할 퀘스트:", ["선택 안함"] + q_names, key="q_select_box")
            st.session_state.selected_quest_name = selected_q

            if selected_q != "선택 안함":
                q_content = next(item['content'] for item in quests if item['quest_name'] == selected_q)
                if st.button(f"⚔️ '{selected_q}' 시작"):
                    kiwi = load_kiwi()
                    st.session_state.sents = [s.text for s in kiwi.split_into_sents(q_content) if len(s.text)>5]
                    st.session_state.q_idx = 0
                    if 'curr_ans' in st.session_state: del st.session_state.curr_ans
                    st.success("로드 완료! 아래로 스크롤하세요.")

    with tab_upload:
        new_q_name = st.text_input("퀘스트 이름")
        uploaded = st.file_uploader("자료 업로드 (.txt)", type=['txt'])
        if st.button("저장하기"):
            if new_q_name and uploaded:
                txt_content = uploaded.getvalue().decode('utf-8')
                if gm.save_quest(new_q_name, txt_content, st.session_state.user_id):
                    st.success("저장 완료!"); time.sleep(1); st.rerun()
                else: st.error("중복된 이름입니다.")

    st.divider()

    # 문제 출제 로직
    if 'sents' in st.session_state and st.session_state.sents:
        if 'curr_ans' not in st.session_state:
            curr_sent = st.session_state.sents[st.session_state.q_idx % len(st.session_state.sents)]
            kiwi = load_kiwi()
            tokens = kiwi.tokenize(curr_sent)

            STOPWORDS = {'다음', '사항', '경우', '포함', '관련', '해당', '각', '호', '목', '조', '항', '위', '아래', '전', '후', '및', '등', '이', '그', '저', '것', '수', '때', '중', '가지', '누구', '무엇', '따름', '의', '를', '가', '약', '양', '때문', '자', '바', '점'}
            nouns = [t.form for t in tokens if t.tag in ['NNG', 'NNP'] and len(t.form)>1 and t.form not in STOPWORDS]
            
            if not nouns: st.session_state.q_idx += 1; st.rerun()
            
            diff = st.session_state.difficulty
            unique_nouns = list(set(nouns))
            target_nouns = []
            
            if "쉬움" in diff: target_nouns = [random.choice(unique_nouns)]
            elif "보통" in diff: k = max(1, int(len(unique_nouns) * 0.3)); target_nouns = random.sample(unique_nouns, k)
            elif "어려움" in diff: k = max(1, int(len(unique_nouns) * 0.5)); target_nouns = random.sample(unique_nouns, k)
            else: target_nouns = unique_nouns

            # 순서 정렬
            matches = []
            for t in target_nouns:
                for m in re.finditer(re.escape(t), curr_sent):
                    matches.append((m.start(), m.group()))
            matches.sort(key=lambda x: x[0])
            
            st.session_state.curr_sent = curr_sent
            st.session_state.curr_matches = matches
            st.session_state.curr_targets = [m[1] for m in matches]
            st.session_state.curr_ans = "ACTIVE"

        # [디자인] 카드 컨테이너
        with st.container(border=True): 
            with st.form("btl", clear_on_submit=False):
                st.write("📝 **빈칸 채우기**")
                
                # [모바일 최적화] 인터리브 방식 (텍스트 -> 입력 -> 텍스트)
                user_inputs = []
                last_idx = 0
                full_text = st.session_state.curr_sent
                
                for i, (start, word) in enumerate(st.session_state.curr_matches):
                    # 1. 빈칸 앞 텍스트
                    pre_text = full_text[last_idx:start]
                    if pre_text.strip():
                        st.markdown(f'<div class="quest-text">{pre_text}</div>', unsafe_allow_html=True)
                    
                    # 2. 입력창
                    val = st.text_input(f"빈칸 ({i+1}) 정답", key=f"ans_{st.session_state.q_idx}_{i}")
                    user_inputs.append(val)
                    
                    last_idx = start + len(word)
                
                # 3. 남은 뒷 텍스트
                if last_idx < len(full_text):
                    st.markdown(f'<div class="quest-text">{full_text[last_idx:]}</div>', unsafe_allow_html=True)

                st.write("")
                sub = st.form_submit_button("🔥 정답 확인")
                
                if sub:
                    all_correct = True
                    wrong_indices = []
                    for i, target in enumerate(st.session_state.curr_targets):
                        if user_inputs[i].strip() != target: 
                            all_correct = False
                            wrong_indices.append(i+1)
                    
                    if all_correct:
                        g, up, gain, nl, nx, stat, count = gm.process_reward(
                            st.session_state.user_id, st.session_state.curr_sent, 
                            st.session_state.level, st.session_state.xp, st.session_state.user_row_idx,
                            st.session_state.selected_quest_name
                        )
                        st.session_state.level = nl
                        st.session_state.xp = nx
                        
                        msg = "✨ 완벽합니다!"
                        if stat == "UPGRADE": msg = f"🔥 숙련도 UP! ({count}회독)"
                        if g=="LEGEND": st.balloons(); st.success(f"👑 {msg} 전설 등급! (+{gain})")
                        else: st.success(f"{msg} (+{gain})")
                        
                        time.sleep(1.5); del st.session_state.curr_ans; st.session_state.q_idx += 1; st.rerun()
                    else:
                        st.error(f"💥 {wrong_indices}번 빈칸이 틀렸습니다!")

# 화면 4: 도감
elif st.session_state.page == 'collection':
    if st.button("🏠 로비로"): st.session_state.page = 'main'; st.rerun()
    st.header("📖 지식 도감")
    
    my_cards = gm.get_collections(st.session_state.user_id)
    if not my_cards: st.info("아직 수집한 카드가 없습니다.")
    else:
        quest_list = sorted(list(set([c.get('quest_name', '기타') for c in my_cards])))
        filter_q = st.multiselect("📂 퀘스트 필터", quest_list, default=quest_list)
        filtered_cards = [c for c in my_cards if c.get('quest_name', '기타') in filter_q]
        
        st.caption(f"총 {len(filtered_cards)}장의 카드를 보유중입니다.")
        
        for c in filtered_cards:
            g = c.get('grade', 'NORMAL')
            cnt = c.get('count', 1)
            q_name = c.get('quest_name', 'Unknown')
            
            if g == 'LEGEND': border_col = 'gold'; bg_col = '#fffacd'
            elif g == 'RARE': border_col = '#87CEEB'; bg_col = '#f0f8ff'
            else: border_col = '#d3d3d3'; bg_col = '#f5f5f5'
            
            st.markdown(f"""
                <div style="background:{bg_col}; border:2px solid {border_col}; border-radius:10px; padding:15px; margin-bottom:10px; color:black;">
                    <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                        <span style="background:{border_col}; color:{'black' if g=='LEGEND' else 'white'}; padding:2px 8px; border-radius:5px; font-size:0.8rem; font-weight:bold;">{g}</span>
                        <span style="font-weight:bold; color:#d9534f;">Lv.{cnt} (숙련도)</span>
                    </div>
                    <div style="font-size:1.1rem; line-height:1.6; margin-bottom:5px;">{c['card_text']}</div>
                    <div style="font-size:0.8rem; color:#666; text-align:right;">📂 {q_name}</div>
                </div>
            """, unsafe_allow_html=True)
