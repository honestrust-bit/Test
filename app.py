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
# [Backend] 구글 시트 매니저 (캐싱 적용으로 429 오류 해결!)
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
            
            # 시트 연결 및 자동 복구
            try: self.users_ws = self.sheet.worksheet("users")
            except: self.users_ws = self.sheet.add_worksheet("users", 100, 10)
            if not self.users_ws.row_values(1): self.users_ws.append_row(["user_id", "password", "level", "xp", "title"])
            
            try: self.collections_ws = self.sheet.worksheet("collections")
            except: self.collections_ws = self.sheet.add_worksheet("collections", 100, 10)
            
            # 도감 헤더 체크
            headers = ["user_id", "card_text", "grade", "collected_at", "quest_name", "count"]
            if not self.collections_ws.row_values(1): self.collections_ws.append_row(headers)

            try: self.quests_ws = self.sheet.worksheet("quests")
            except: self.quests_ws = self.sheet.add_worksheet("quests", 100, 5)
            if not self.quests_ws.row_values(1): self.quests_ws.append_row(["quest_name", "content", "created_by", "created_at"])

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
        try: records = self.collections_ws.get_all_records()
        except: records = []
        
        found_idx = -1
        current_count = 0
        current_grade = "NORMAL"
        
        for i, row in enumerate(records):
            if str(row['user_id']) == str(user_id) and row['card_text'] == card_text and row.get('quest_name') == quest_name:
                found_idx = i + 2; current_count = row.get('count', 1); current_grade = row.get('grade', 'NORMAL'); break
        
        status = ""; final_grade = current_grade
        
        if found_idx != -1:
            new_count = current_count + 1
            if new_count >= 7: new_grade = "LEGEND"
            elif new_count >= 3: new_grade = "RARE"
            else: new_grade = current_grade
            self.collections_ws.update_cell(found_idx, 6, new_count)
            self.collections_ws.update_cell(found_idx, 3, new_grade)
            self.collections_ws.update_cell(found_idx, 4, str(datetime.date.today()))
            status = "UPGRADE"; final_grade = new_grade; xp_gain = 10 + (new_count * 2)
        else:
            rand = random.random()
            if rand < 0.05: final_grade = "LEGEND"
            elif rand < 0.20: final_grade = "RARE"
            else: final_grade = "NORMAL"
            self.collections_ws.append_row([user_id, card_text, final_grade, str(datetime.date.today()), quest_name, 1])
            status = "NEW"; xp_gain = 50 if final_grade == "LEGEND" else 30 if final_grade == "RARE" else 20

        new_xp = current_xp + xp_gain
        new_level, req_xp = current_level, current_level * 100
        if new_xp >= req_xp: new_level += 1; new_xp -= req_xp
        
        self.users_ws.update_cell(row_idx, 3, new_level)
        self.users_ws.update_cell(row_idx, 4, new_xp)
        return final_grade, xp_gain, new_level, new_xp, status, current_count + 1 if found_idx != -1 else 1

    def get_collections(self, user_id):
        try: return [c for c in self.collections_ws.get_all_records() if str(c['user_id']) == str(user_id)]
        except: return []

# ==========================================
# [Design] 메이플 스타일 적용 🍁
# ==========================================
def apply_game_style():
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Jua&display=swap');
        
        html, body, [class*="css"] { font-family: 'Jua', sans-serif; }

        /* 배경: 헤네시스 느낌 (하늘 + 언덕) */
        .stApp {
            background: linear-gradient(180deg, #87CEEB 0%, #87CEEB 70%, #90EE90 70%, #90EE90 100%);
        }

        /* 메인 컨테이너 (UI 창 느낌) */
        .main-container {
            background-color: rgba(255, 255, 255, 0.9);
            border: 3px solid #666;
            border-radius: 15px;
            padding: 20px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        }

        /* 카드/퀘스트 보드 (반투명 검정 - 메이플 UI 스타일) */
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background-color: rgba(0, 0, 0, 0.6) !important;
            border: 2px solid #ccc !important;
            border-radius: 10px !important;
            padding: 20px !important;
        }
        
        /* 텍스트 색상 (어두운 배경이라 흰색으로) */
        div[data-testid="stVerticalBlockBorderWrapper"] p,
        div[data-testid="stVerticalBlockBorderWrapper"] span,
        div[data-testid="stVerticalBlockBorderWrapper"] div {
            color: #ffffff !important;
            font-size: 1.1rem;
        }

        /* 버튼 (입체감 있는 오렌지 버튼) */
        .stButton > button {
            background: linear-gradient(to bottom, #FFA500, #FF8C00);
            color: white;
            border: 2px solid #fff;
            border-radius: 10px;
            height: 50px;
            font-size: 1.2rem;
            box-shadow: 0 4px 0 #CD6600; /* 입체 그림자 */
            transition: all 0.1s;
        }
        .stButton > button:active {
            transform: translateY(4px);
            box-shadow: 0 0 0 #CD6600;
        }
        
        /* 입력창 (깔끔한 흰색) */
        .stTextInput input {
            background-color: #fff;
            color: #333;
            border-radius: 5px;
            border: 2px solid #888;
        }
        .stTextInput label { color: #fff !important; }

        /* 경험치 바 (노란색/금색) */
        .stProgress > div > div > div > div {
            background: linear-gradient(to right, #FFD700, #FFA500);
        }

        /* 빈칸 번호표 */
        .blank-number {
            background-color: #FF4500;
            color: white;
            padding: 2px 6px;
            border-radius: 5px;
            font-weight: bold;
            margin-right: 5px;
            font-size: 1rem;
        }
        
        /* 아바타 둥둥 */
        @keyframes float { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-10px); } }
        .avatar-emoji { font-size: 100px; animation: float 2.5s ease-in-out infinite; filter: drop-shadow(0 5px 10px rgba(0,0,0,0.3)); }
        </style>
    """, unsafe_allow_html=True)

# ==========================================
# [Logic] 캐싱된 매니저 로드 (429 에러 방지)
# ==========================================
st.set_page_config(page_title="메모리 가디언즈", page_icon="🍁", layout="centered")
apply_game_style()

@st.cache_resource
def load_resources():
    return Kiwi(), GoogleSheetManager()

kiwi, gm = load_resources()
cookie_manager = stx.CookieManager()

# 세션 초기화
if 'user_id' not in st.session_state:
    st.session_state.user_id = None
    st.session_state.difficulty = "쉬움 (빈칸 1개)"

time.sleep(0.1)
cookie_id = cookie_manager.get("my_game_id")
if st.session_state.user_id is None and cookie_id:
    # 빠른 로그인을 위해 검증 생략하고 ID만 세팅 (실제 서비스라면 토큰 검증 필요)
    try:
        records = gm.users_ws.get_all_records()
        for i, row in enumerate(records):
            if str(row['user_id']) == str(cookie_id):
                st.session_state.user_id = row['user_id']
                st.session_state.user_row_idx = i + 2
                st.session_state.level = row['level']
                st.session_state.xp = row['xp']
                st.toast(f"🍁 접속 성공: {cookie_id}", icon="✅"); break
    except: pass

# 화면 1: 로그인
if st.session_state.user_id is None:
    st.title("🍁 메모리 가디언즈")
    st.markdown("<div style='text-align:center; color:#333;'>나만의 지식을 키우는 모험을 시작하세요!</div>", unsafe_allow_html=True)
    st.write("")
    
    tab1, tab2 = st.tabs(["로그인", "모험가 등록"])
    with tab1:
        lid = st.text_input("아이디")
        lpw = st.text_input("비밀번호", type="password")
        remember_me = st.checkbox("로그인 유지")
        if st.button("게임 시작", type="primary"):
            user_data, row_idx = gm.login(lid, lpw)
            if user_data:
                st.session_state.user_id = lid
                st.session_state.user_row_idx = row_idx
                st.session_state.level = user_data['level']
                st.session_state.xp = user_data['xp']
                if remember_me: cookie_manager.set("my_game_id", lid, expires_at=datetime.datetime.now() + datetime.timedelta(days=7))
                st.rerun()
            else: st.error("아이디 또는 비밀번호를 확인해주세요.")
    with tab2:
        rid = st.text_input("새 아이디")
        rpw = st.text_input("새 비밀번호", type="password")
        if st.button("등록하기"):
            if gm.register(rid, rpw): st.success("환영합니다! 로그인을 진행해주세요."); time.sleep(1); st.rerun()
            else: st.error("이미 사용 중인 아이디입니다.")

# 화면 2: 로비
elif 'page' not in st.session_state or st.session_state.page == 'main':
    u_id, lv, xp = st.session_state.user_id, st.session_state.level, st.session_state.xp
    req_xp = lv * 100
    
    # 아바타 (메이플 느낌 몬스터)
    if lv < 5: avatar = "🍄"      # 주황버섯 느낌
    elif lv < 10: avatar = "🐷"    # 리본돼지 느낌
    elif lv < 20: avatar = "👻"    # 레이스 느낌
    else: avatar = "🐉"           # 혼테일/자쿰 느낌
    
    col_top1, col_top2 = st.columns([3, 1])
    with col_top1:
        diff = st.select_slider("🔥 사냥터 난이도", options=["쉬움 (빈칸 1개)", "보통 (30%)", "어려움 (50%)", "지옥 (전부)"])
        st.session_state.difficulty = diff
    with col_top2:
        if st.button("로그아웃"):
            cookie_manager.delete("my_game_id")
            st.session_state.user_id = None
            st.rerun()
            
    st.markdown(f"""
        <div class="main-avatar-container">
            <div class="avatar-emoji">{avatar}</div>
            <div style="background:rgba(0,0,0,0.7); color:white; padding:5px 15px; border-radius:15px; margin-top:10px;">
                Lv.{lv} <b>{u_id}</b>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    # 경험치 바 (EXP)
    st.write(f"**EXP** ({xp} / {req_xp})")
    st.progress(min(xp / req_xp, 1.0))

    col1, col2 = st.columns(2)
    with col1:
        if st.button("⚔️ 퀘스트 사냥"): st.session_state.page = 'dungeon'; st.rerun()
    with col2:
        if st.button("📖 몬스터 도감"): st.session_state.page = 'collection'; st.rerun()

# 화면 3: 퀘스트 (인터리브 방식 - 모바일 최적화)
elif st.session_state.page == 'dungeon':
    if st.button("🏠 마을로 귀환"): 
        st.session_state.page = 'main'
        if 'curr_ans' in st.session_state: del st.session_state.curr_ans
        st.rerun()
        
    st.header("📜 퀘스트 게시판")
    tab_list, tab_upload = st.tabs(["퀘스트 받기", "퀘스트 만들기"])
    
    with tab_list:
        quests = gm.get_quest_list()
        if not quests: st.info("수행할 퀘스트가 없습니다.")
        else:
            q_names = [q['quest_name'] for q in quests]
            if 'selected_quest_name' not in st.session_state: st.session_state.selected_quest_name = "선택 안함"
            selected_q = st.selectbox("진행할 퀘스트:", ["선택 안함"] + q_names)
            st.session_state.selected_quest_name = selected_q

            if selected_q != "선택 안함":
                q_content = next(item['content'] for item in quests if item['quest_name'] == selected_q)
                if st.button(f"⚔️ '{selected_q}' 사냥 시작"):
                    st.session_state.sents = [s.text for s in kiwi.split_into_sents(q_content) if len(s.text)>5]
                    st.session_state.q_idx = 0
                    if 'curr_ans' in st.session_state: del st.session_state.curr_ans
                    st.rerun()

    with tab_upload:
        new_q_name = st.text_input("퀘스트 이름")
        uploaded = st.file_uploader("자료 업로드 (.txt)", type=['txt'])
        if st.button("저장하기"):
            if new_q_name and uploaded:
                txt_content = uploaded.getvalue().decode('utf-8')
                if gm.save_quest(new_q_name, txt_content, st.session_state.user_id):
                    st.success("퀘스트 등록 완료!"); time.sleep(1); st.rerun()
                else: st.error("이미 존재하는 이름입니다.")

    st.divider()

    # 문제 출제
    if 'sents' in st.session_state and st.session_state.sents:
        if 'curr_ans' not in st.session_state:
            curr_sent = st.session_state.sents[st.session_state.q_idx % len(st.session_state.sents)]
            tokens = kiwi.tokenize(curr_sent)
            STOPWORDS = {'다음','사항','경우','포함','관련','해당','각','호','목','조','항','위','아래','전','후','및','등','이','그','저','것','수','때','중','가지','누구','무엇','따름','의','를','가'}
            nouns = [t.form for t in tokens if t.tag in ['NNG', 'NNP'] and len(t.form)>1 and t.form not in STOPWORDS]
            
            if not nouns: st.session_state.q_idx += 1; st.rerun()
            
            diff = st.session_state.difficulty
            unique_nouns = list(set(nouns))
            target_nouns = []
            if "쉬움" in diff: target_nouns = [random.choice(unique_nouns)]
            elif "보통" in diff: k = max(1, int(len(unique_nouns) * 0.3)); target_nouns = random.sample(unique_nouns, k)
            elif "어려움" in diff: k = max(1, int(len(unique_nouns) * 0.5)); target_nouns = random.sample(unique_nouns, k)
            else: target_nouns = unique_nouns

            matches = []
            for t in target_nouns:
                for m in re.finditer(re.escape(t), curr_sent): matches.append((m.start(), m.group()))
            matches.sort(key=lambda x: x[0])
            
            st.session_state.curr_sent = curr_sent
            st.session_state.curr_matches = matches
            st.session_state.curr_targets = [m[1] for m in matches]
            st.session_state.curr_ans = "ACTIVE"

        # [카드형 컨테이너] (검은색 반투명)
        with st.container(border=True): 
            with st.form("btl", clear_on_submit=False):
                # 인터리브 방식: 텍스트 -> 입력 -> 텍스트
                user_inputs = []
                last_idx = 0
                full_text = st.session_state.curr_sent
                
                for i, (start, word) in enumerate(st.session_state.curr_matches):
                    pre_text = full_text[last_idx:start]
                    if pre_text: st.write(pre_text) # 앞부분 텍스트
                    
                    # 입력창 (빈칸 바로 아래)
                    col_blank, col_rest = st.columns([1, 0.1])
                    with col_blank:
                        val = st.text_input(f"빈칸 ({i+1}) 정답", key=f"ans_{st.session_state.q_idx}_{i}", placeholder="여기에 정답 입력")
                    user_inputs.append(val)
                    last_idx = start + len(word)
                
                if last_idx < len(full_text): st.write(full_text[last_idx:]) # 남은 텍스트
                
                st.write("")
                if st.form_submit_button("🔥 공격하기"):
                    all_correct = True; wrong_indices = []
                    for i, target in enumerate(st.session_state.curr_targets):
                        if user_inputs[i].strip() != target: all_correct = False; wrong_indices.append(i+1)
                    
                    if all_correct:
                        g, gain, nl, nx, stat, cnt = gm.process_reward(
                            st.session_state.user_id, st.session_state.curr_sent, 
                            st.session_state.level, st.session_state.xp, st.session_state.user_row_idx,
                            st.session_state.selected_quest_name
                        )
                        st.session_state.level = nl; st.session_state.xp = nx
                        
                        msg = "Critical Hit! ✨"
                        if stat == "UPGRADE": msg = f"Skill Up! 🔥 ({cnt}회독)"
                        if g=="LEGEND": st.balloons(); st.success(f"👑 {msg} 전설 등급! (+{gain} EXP)")
                        else: st.success(f"{msg} (+{gain} EXP)")
                        
                        time.sleep(1.5); del st.session_state.curr_ans; st.session_state.q_idx += 1; st.rerun()
                    else: st.error(f"Miss! 💥 {wrong_indices}번이 틀렸습니다.")

# 화면 4: 도감
elif st.session_state.page == 'collection':
    if st.button("🏠 마을로 귀환"): st.session_state.page = 'main'; st.rerun()
    st.header("📖 몬스터 도감")
    
    my_cards = gm.get_collections(st.session_state.user_id)
    if not my_cards: st.info("아직 사냥한 몬스터가 없습니다.")
    else:
        quest_list = sorted(list(set([c.get('quest_name', '기타') for c in my_cards])))
        filter_q = st.multiselect("📂 던전 필터", quest_list, default=quest_list)
        filtered_cards = [c for c in my_cards if c.get('quest_name', '기타') in filter_q]
        
        st.caption(f"총 {len(filtered_cards)} 마리 수집")
        
        for c in filtered_cards:
            g = c.get('grade', 'NORMAL')
            cnt = c.get('count', 1)
            q_name = c.get('quest_name', 'Unknown')
            
            # 메이플 아이템 등급 색상
            if g == 'LEGEND': border_col = '#32CD32'; bg_col = 'rgba(50, 205, 50, 0.1)' # 유니크(초록)
            elif g == 'RARE': border_col = '#00BFFF'; bg_col = 'rgba(0, 191, 255, 0.1)' # 레어(파랑)
            else: border_col = '#A9A9A9'; bg_col = 'rgba(169, 169, 169, 0.1)' # 노멀
            
            st.markdown(f"""
                <div style="background:{bg_col}; border:2px solid {border_col}; border-radius:10px; padding:15px; margin-bottom:10px; color:white;">
                    <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                        <span style="background:{border_col}; color:white; padding:2px 8px; border-radius:5px; font-weight:bold;">{g}</span>
                        <span style="font-weight:bold; color:#FFD700;">Lv.{cnt}</span>
                    </div>
                    <div style="font-size:1.1rem; line-height:1.6; margin-bottom:5px; color:#fff;">{c['card_text']}</div>
                    <div style="font-size:0.8rem; color:#ccc; text-align:right;">📂 {q_name}</div>
                </div>
            """, unsafe_allow_html=True)
