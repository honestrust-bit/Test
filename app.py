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
# [Backend] 구글 시트 매니저
# ==========================================
class GoogleSheetManager:
    def __init__(self):
        try:
            scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
            # Secrets에서 인증 정보 가져오기
            if "gcp_service_account" in st.secrets:
                creds_dict = dict(st.secrets["gcp_service_account"])
            else:
                st.error("Secrets 설정이 필요합니다."); st.stop()
                
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            self.client = gspread.authorize(creds)
            self.sheet = self.client.open("memory_game_db")
            
            # 1. 유저 시트
            try: self.users_ws = self.sheet.worksheet("users")
            except: self.users_ws = self.sheet.add_worksheet("users", 100, 10); self.users_ws.append_row(["user_id", "password", "level", "xp", "title"])
            
            # 2. 도감 시트 (구조: 유저, 내용, 등급, 날짜, 퀘스트명, 숙련도)
            try: self.collections_ws = self.sheet.worksheet("collections")
            except: 
                self.collections_ws = self.sheet.add_worksheet("collections", 100, 10)
                self.collections_ws.append_row(["user_id", "card_text", "grade", "collected_at", "quest_name", "count"])

            # 3. 퀘스트 저장소 시트
            try: self.quests_ws = self.sheet.worksheet("quests")
            except: 
                self.quests_ws = self.sheet.add_worksheet("quests", 100, 5)
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

    # [핵심 로직] 보상 처리 및 숙련도(Mastery) 시스템
    def process_reward(self, user_id, card_text, current_level, current_xp, row_idx, quest_name):
        records = self.collections_ws.get_all_records()
        found_idx = -1
        current_count = 0
        current_grade = "NORMAL"
        
        # 중복 카드 체크
        for i, row in enumerate(records):
            if str(row['user_id']) == str(user_id) and row['card_text'] == card_text and row.get('quest_name') == quest_name:
                found_idx = i + 2 
                current_count = row.get('count', 1)
                current_grade = row.get('grade', 'NORMAL')
                break
        
        status = ""
        final_grade = current_grade
        
        # A. 이미 있는 카드 -> 숙련도 증가 & 등급 승급
        if found_idx != -1:
            new_count = current_count + 1
            # 승급 기준: 3회 이상 Rare, 7회 이상 Legend
            if new_count >= 7: new_grade = "LEGEND"
            elif new_count >= 3: new_grade = "RARE"
            else: new_grade = current_grade
            
            self.collections_ws.update_cell(found_idx, 6, new_count) # count
            self.collections_ws.update_cell(found_idx, 3, new_grade) # grade
            self.collections_ws.update_cell(found_idx, 4, str(datetime.date.today()))
            
            status = "UPGRADE"
            final_grade = new_grade
            xp_gain = 10 + (new_count * 2) # 반복 학습 경험치
            
        # B. 새 카드 획득
        else:
            rand = random.random()
            if rand < 0.05: final_grade = "LEGEND"
            elif rand < 0.20: final_grade = "RARE"
            else: final_grade = "NORMAL"
            
            self.collections_ws.append_row([user_id, card_text, final_grade, str(datetime.date.today()), quest_name, 1])
            status = "NEW"
            xp_gain = 50 if final_grade == "LEGEND" else 30 if final_grade == "RARE" else 20

        # 경험치 반영
        new_xp = current_xp + xp_gain
        new_level, req_xp = current_level, current_level * 100
        
        is_levelup = False
        if new_xp >= req_xp:
            new_level += 1; new_xp -= req_xp; is_levelup = True
            
        self.users_ws.update_cell(row_idx, 3, new_level)
        self.users_ws.update_cell(row_idx, 4, new_xp)
        
        return final_grade, is_levelup, xp_gain, new_level, new_xp, status, current_count + 1 if found_idx != -1 else 1

    def get_collections(self, user_id):
        all_cards = self.collections_ws.get_all_records()
        return [c for c in all_cards if str(c['user_id']) == str(user_id)]

# ==========================================
# [UI] 스타일 (CSS 오류 수정 완료)
# ==========================================
def apply_game_style():
    st.markdown("""
        <link href="https://fonts.googleapis.com/css2?family=Jua&display=swap" rel="stylesheet">
        <style>
        /* 기본 배경 */
        .stApp { 
            background: linear-gradient(to bottom, #1a1a2e, #16213e, #0f3460); 
            color: #ffffff; 
            font-family: 'Jua', sans-serif; 
        }
        
        /* 아바타 영역 */
        .main-avatar-container { 
            display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 20px 0; 
        }
        .avatar-emoji { 
            font-size: 80px; animation: float 3s ease-in-out infinite; 
        }
        .user-info-box { 
            background: rgba(0,0,0,0.5); padding: 5px 15px; border-radius: 20px; border: 2px solid #FFD700; margin-top: 10px; 
        }
        
        /* 버튼 공통 */
        .stButton > button { 
            width: 100%; height: 50px; border-radius: 10px; font-family: 'Jua'; font-size: 1.1rem; 
        }
        
        /* [중요] 카드형 컨테이너 디자인 */
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background-color: #fff8dc !important;
            border: 4px solid #8b4513 !important;
            border-radius: 15px !important;
            padding: 20px !important;
        }
        
        /* 카드 내부 텍스트 강제 갈색 */
        div[data-testid="stVerticalBlockBorderWrapper"] * {
            color: #3d2b07 !important;
            font-family: 'Jua', sans-serif !important;
        }
        
        /* 입력창 라벨 */
        .stTextInput label {
            color: #3d2b07 !important;
        }

        /* 둥둥 떠다니는 효과 */
        @keyframes float { 
            0%, 100% { transform: translateY(0); } 
            50% { transform: translateY(-10px); } 
        }
        </style>
    """, unsafe_allow_html=True)

# ==========================================
# [Main] 앱 실행 로직
# ==========================================
st.set_page_config(page_title="메모리 가디언즈", page_icon="📘", layout="centered")
apply_game_style()

@st.cache_resource
def load_kiwi(): return Kiwi()

gm = GoogleSheetManager()
cookie_manager = stx.CookieManager()

# 세션 상태 초기화
if 'user_id' not in st.session_state:
    st.session_state.user_id = None
    st.session_state.difficulty = "쉬움 (빈칸 1개)"

# 자동 로그인 로직
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

# ---------------------------------------------------------
# 화면 1: 로그인
# ---------------------------------------------------------
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

# ---------------------------------------------------------
# 화면 2: 메인 로비
# ---------------------------------------------------------
elif 'page' not in st.session_state or st.session_state.page == 'main':
    u_id, lv, xp = st.session_state.user_id, st.session_state.level, st.session_state.xp
    req_xp = lv * 100
    
    if lv < 5: avatar = "📜" 
    elif lv < 10: avatar = "📘"
    elif lv < 20: avatar = "📚"
    else: avatar = "🏛️"
    
    col_top1, col_top2 = st.columns([3, 1])
    with col_top1:
        diff = st.select_slider("🔥 난이도 설정", options=["쉬움 (빈칸 1개)", "보통 (30%)", "어려움 (50%)", "지옥 (전부)"])
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

# ---------------------------------------------------------
# 화면 3: 퀘스트 던전 (완전 정복 모드 + 순서 정렬 + 카드 내 입력)
# ---------------------------------------------------------
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

    # [문제 출제 로직]
    if 'sents' in st.session_state and st.session_state.sents:
        if 'curr_ans' not in st.session_state:
            curr_sent = st.session_state.sents[st.session_state.q_idx % len(st.session_state.sents)]
            kiwi = load_kiwi()
            tokens = kiwi.tokenize(curr_sent)

            # 금지어 설정
            STOPWORDS = {
                '다음', '사항', '경우', '포함', '관련', '해당', '각', '호', '목', '조', '항', 
                '위', '아래', '전', '후', '및', '등', '이', '그', '저', '것', '수', '때', 
                '중', '가지', '누구', '무엇', '따름', '의', '를', '가', '약', '양', '때문', '자', '바', '점'
            }

            nouns = [t.form for t in tokens if t.tag in ['NNG', 'NNP'] and len(t.form)>1 and t.form not in STOPWORDS]
            
            if not nouns: st.session_state.q_idx += 1; st.rerun()
            
            # 난이도별 타겟 선정
            diff = st.session_state.difficulty
            unique_nouns = list(set(nouns))
            target_nouns = []
            
            if "쉬움" in diff: target_nouns = [random.choice(unique_nouns)]
            elif "보통" in diff: k = max(1, int(len(unique_nouns) * 0.3)); target_nouns = random.sample(unique_nouns, k)
            elif "어려움" in diff: k = max(1, int(len(unique_nouns) * 0.5)); target_nouns = random.sample(unique_nouns, k)
            else: target_nouns = unique_nouns

            # [순서 정렬 핵심 로직]
            matches = []
            for t in target_nouns:
                for m in re.finditer(re.escape(t), curr_sent):
                    matches.append((m.start(), m.group()))
            
            matches.sort(key=lambda x: x[0]) # 인덱스 순 정렬
            
            # 앞에서부터 (1), (2) 번호 매기며 치환
            temp_sent_list = list(curr_sent)
            matches.reverse() # 뒤에서부터 치환해야 인덱스 안꼬임
            processed_indices = set()
            blank_counter = len(matches)
            real_targets_ordered = []

            for idx, word in matches:
                if idx in processed_indices: continue
                blank_html = f' **( {blank_counter} )** ________ ' # 번호 강조
                temp_sent_list[idx : idx + len(word)] = list(blank_html)
                real_targets_ordered.append(word)
                blank_counter -= 1
            
            q_html = "".join(temp_sent_list)
            real_targets_ordered.reverse() # 정답 리스트는 다시 앞 순서대로

            st.session_state.curr_sent = curr_sent
            st.session_state.curr_targets = real_targets_ordered
            st.session_state.curr_html = q_html
            st.session_state.curr_ans = "ACTIVE"

        # [카드 컨테이너] 문장 + 입력창 결합
        with st.container(border=True): # 여기가 카드 모양이 됩니다
            st.markdown(st.session_state.curr_html)
            st.divider()
            
            with st.form("btl", clear_on_submit=False):
                st.write("📝 **빈칸 채우기**")
                cols = st.columns(min(len(st.session_state.curr_targets), 2))
                user_inputs = []
                
                for i in range(len(st.session_state.curr_targets)):
                    with cols[i % 2]:
                        # key에 q_idx 포함 -> 문제 바뀌면 자동 초기화
                        val = st.text_input(f"빈칸 ({i+1}) 정답", key=f"ans_{st.session_state.q_idx}_{i}")
                        user_inputs.append(val)
                
                sub = st.form_submit_button("🔥 정답 확인")
                
                if sub:
                    all_correct = True
                    wrong_indices = []
                    for i, target in enumerate(st.session_state.curr_targets):
                        if user_inputs[i].strip() != target: # 공백 제거 후 비교
                            all_correct = False
                            wrong_indices.append(i+1)
                    
                    if all_correct:
                        # 보상 지급 & 숙련도 체크
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

# ---------------------------------------------------------
# 화면 4: 도감 (퀘스트 필터 + 숙련도 표시)
# ---------------------------------------------------------
elif st.session_state.page == 'collection':
    if st.button("🏠 로비로"): st.session_state.page = 'main'; st.rerun()
    st.header("📖 지식 도감")
    
    my_cards = gm.get_collections(st.session_state.user_id)
    if not my_cards: st.info("아직 수집한 카드가 없습니다.")
    else:
        # 필터링
        quest_list = sorted(list(set([c.get('quest_name', '기타') for c in my_cards])))
        filter_q = st.multiselect("📂 퀘스트 필터", quest_list, default=quest_list)
        filtered_cards = [c for c in my_cards if c.get('quest_name', '기타') in filter_q]
        
        st.caption(f"총 {len(filtered_cards)}장의 카드를 보유중입니다.")
        
        for c in filtered_cards:
            g = c.get('grade', 'NORMAL')
            cnt = c.get('count', 1)
            q_name = c.get('quest_name', 'Unknown')
            
            # 등급별 색상
            if g == 'LEGEND': border_col = 'gold'; bg_col = '#fffacd'
            elif g == 'RARE': border_col = '#87CEEB'; bg_col = '#f0f8ff'
            else: border_col = '#d3d3d3'; bg_col = '#f5f5f5'
            
            # 도감 카드 디자인
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
