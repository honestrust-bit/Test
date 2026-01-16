import streamlit as st
import random
import time
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from kiwipiepy import Kiwi
import extra_streamlit_components as stx
import datetime

# ==========================================
# [Backend] 구글 시트 매니저
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
            
            try: self.users_ws = self.sheet.worksheet("users")
            except: self.users_ws = self.sheet.add_worksheet("users", 100, 10); self.users_ws.append_row(["user_id", "password", "level", "xp", "title"])
            
            try: self.collections_ws = self.sheet.worksheet("collections")
            except: self.collections_ws = self.sheet.add_worksheet("collections", 100, 10); self.collections_ws.append_row(["user_id", "card_text", "grade", "collected_at"])

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

    def process_reward(self, user_id, card_text, current_level, current_xp, row_idx):
        rand = random.random()
        if rand < 0.05: grade = "LEGEND"
        elif rand < 0.20: grade = "RARE"
        else: grade = "NORMAL"
        
        xp_gain = 50 if grade == "LEGEND" else 30 if grade == "RARE" else 10
        new_xp = current_xp + xp_gain
        new_level, req_xp = current_level, current_level * 100
        
        is_levelup = False
        if new_xp >= req_xp:
            new_level += 1; new_xp -= req_xp; is_levelup = True
            
        self.users_ws.update_cell(row_idx, 3, new_level)
        self.users_ws.update_cell(row_idx, 4, new_xp)
        self.collections_ws.append_row([user_id, card_text, grade, str(datetime.date.today())])
        return grade, is_levelup, xp_gain, new_level, new_xp

    def get_collections(self, user_id):
        all_cards = self.collections_ws.get_all_records()
        return [c for c in all_cards if str(c['user_id']) == str(user_id)]

# ==========================================
# [UI] 스타일
# ==========================================
def apply_game_style():
    st.markdown("""
        <link href="https://fonts.googleapis.com/css2?family=Jua&display=swap" rel="stylesheet">
        <style>
        .stApp { background: linear-gradient(to bottom, #1a1a2e, #16213e, #0f3460); color: #ffffff; font-family: 'Jua', sans-serif; }
        .main-avatar-container { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 30px 0; }
        .avatar-emoji { font-size: 100px; animation: float 3s ease-in-out infinite; filter: drop-shadow(0 0 20px rgba(255,255,255,0.3)); }
        .user-info-box { background: rgba(0,0,0,0.5); padding: 5px 15px; border-radius: 20px; border: 2px solid #FFD700; margin-top: 10px; }
        .stProgress > div > div > div > div { background: linear-gradient(to right, #00b09b, #96c93d); }
        .stButton > button { width: 100%; height: 50px; border-radius: 10px; font-family: 'Jua'; font-size: 1.1rem; }
        .quiz-card { background-color: #fff8dc; border: 4px solid #8b4513; border-radius: 15px; padding: 25px; margin: 20px auto; color: #3d2b07; font-size: 1.3rem; line-height: 1.8; text-align: center; position: relative;}
        .blank-space { display: inline-block; min-width: 50px; border-bottom: 3px dashed #8b4513; margin: 0 4px; color: transparent; background: rgba(139, 69, 19, 0.1); border-radius: 4px;}
        @keyframes float { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-10px); } }
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

# 세션 초기화
if 'user_id' not in st.session_state:
    st.session_state.user_id = None
    st.session_state.difficulty = "쉬움 (빈칸 1개)"

# 자동 로그인 체크
time.sleep(0.1)
cookie_id = cookie_manager.get("my_game_id")
if st.session_state.user_id is None and cookie_id:
    records = gm.users_ws.get_all_records()
    found = False
    for i, row in enumerate(records):
        if str(row['user_id']) == str(cookie_id):
            st.session_state.user_id = row['user_id']
            st.session_state.user_row_idx = i + 2
            st.session_state.level = row['level']
            st.session_state.xp = row['xp']
            found = True
            break
    if found: st.toast(f"환영합니다! {cookie_id}님", icon="📘")

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

# 화면 2: 메인 로비 (책 테마 적용!)
elif 'page' not in st.session_state or st.session_state.page == 'main':
    u_id, lv, xp = st.session_state.user_id, st.session_state.level, st.session_state.xp
    req_xp = lv * 100
    
    # [변경됨] 책 모양 아바타 진화 시스템
    if lv < 5: avatar = "📜"      # Lv.1~4: 낡은 양피지
    elif lv < 10: avatar = "📘"    # Lv.5~9: 마법서
    elif lv < 20: avatar = "📚"    # Lv.10~19: 지식의 탑
    else: avatar = "🏛️"           # Lv.20~: 지식의 전당
    
    col_top1, col_top2 = st.columns([3, 1])
    with col_top1:
        diff = st.select_slider("🔥 난이도", options=["쉬움 (빈칸 1개)", "보통 (30%)", "어려움 (50%)", "지옥 (전부)"])
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
        if st.button("⚔️ 퀘스트"): st.session_state.page = 'dungeon'; st.rerun()
    with col2:
        if st.button("📖 도감"): st.session_state.page = 'collection'; st.rerun()

# 화면 3: 퀘스트 던전 (금지어 필터 적용!)
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
            selected_q = st.selectbox("진행할 퀘스트:", ["선택 안함"] + q_names)
            if selected_q != "선택 안함":
                q_content = next(item['content'] for item in quests if item['quest_name'] == selected_q)
                if st.button(f"⚔️ '{selected_q}' 시작"):
                    kiwi = load_kiwi()
                    st.session_state.sents = [s.text for s in kiwi.split_into_sents(q_content) if len(s.text)>5]
                    st.session_state.q_idx = 0
                    if 'curr_ans' in st.session_state: del st.session_state.curr_ans
                    st.success("로드 완료!")

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

    # 문제 출제 영역
    if 'sents' in st.session_state and st.session_state.sents:
        if 'curr_ans' not in st.session_state:
            curr_sent = st.session_state.sents[st.session_state.q_idx % len(st.session_state.sents)]
            kiwi = load_kiwi()
            tokens = kiwi.tokenize(curr_sent)

            # [적용됨] 금지어 목록 (빈칸 뚫지 않을 단어들)
            STOPWORDS = {
                '다음', '사항', '경우', '포함', '관련', '해당', '각', '호', '목', '조', '항', 
                '위', '아래', '전', '후', '및', '등', '이', '그', '저', '것', '수', '때', 
                '중', '가지', '누구', '무엇', '따름', '의', '를', '가', '약', '양', '때문', '자', '바'
            }

            # 명사 추출 및 필터링
            nouns = []
            for t in tokens:
                # 일반명사(NNG), 고유명사(NNP)만 허용 (대명사, 의존명사 제외)
                if t.tag in ['NNG', 'NNP']:
                    if len(t.form) > 1: # 2글자 이상
                        if t.form not in STOPWORDS: # 금지어 제외
                            nouns.append(t.form)
            
            if not nouns: st.session_state.q_idx += 1; st.rerun()
            
            # 난이도 적용
            diff = st.session_state.difficulty
            target_nouns = []
            if "쉬움" in diff: target_nouns = [random.choice(nouns)] 
            elif "보통" in diff: k = max(1, int(len(nouns) * 0.3)); target_nouns = random.sample(nouns, k)
            elif "어려움" in diff: k = max(1, int(len(nouns) * 0.5)); target_nouns = random.sample(nouns, k)
            else: target_nouns = list(set(nouns))

            q_html = curr_sent
            for n in target_nouns:
                blank_width = len(n) * 20 
                q_html = q_html.replace(n, f'<span class="blank-space" style="min-width:{blank_width}px;"></span>')

            st.session_state.curr_sent = curr_sent
            st.session_state.curr_targets = target_nouns 
            st.session_state.curr_html = q_html
            st.session_state.curr_ans = target_nouns[0] 

        st.markdown(f"""<div class="quiz-card">{st.session_state.curr_html}</div>""", unsafe_allow_html=True)
        
        with st.form("btl"):
            col_i, col_b = st.columns([3, 1])
            with col_i: inp = st.text_input("정답", placeholder="빈칸 단어 입력", label_visibility="collapsed")
            with col_b: sub = st.form_submit_button("🔥 공격")
            
            if sub:
                is_correct = False
                for t in st.session_state.curr_targets:
                    if t == inp.strip(): is_correct = True; break
                
                if is_correct:
                    g, up, gain, nl, nx = gm.process_reward(st.session_state.user_id, st.session_state.curr_sent, st.session_state.level, st.session_state.xp, st.session_state.user_row_idx)
                    st.session_state.level = nl
                    st.session_state.xp = nx
                    if g=="LEGEND": st.balloons(); st.success(f"👑 전설! (+{gain})")
                    else: st.success(f"✨ 정답! (+{gain})")
                    time.sleep(1); del st.session_state.curr_ans; st.session_state.q_idx += 1; st.rerun()
                else: st.error(f"💥 땡! 정답: {', '.join(st.session_state.curr_targets)}")

# 화면 4: 도감
elif st.session_state.page == 'collection':
    if st.button("🏠 로비로"): st.session_state.page = 'main'; st.rerun()
    st.header("📖 지식 도감")
    cards = gm.get_collections(st.session_state.user_id)
    if not cards: st.info("수집 내역 없음")
    else:
        for c in cards:
            g_short = c['grade'][0]
            st.markdown(f"""
                <div class="quiz-card" style="padding:15px; margin-bottom:10px; border-color:{'gold' if g_short=='L' else 'blue' if g_short=='R' else 'gray'};">
                    <div style="font-weight:bold; color:{'gold' if g_short=='L' else 'blue' if g_short=='R' else 'gray'};">{c['grade']}</div>
                    {c['card_text']}
                </div>
            """, unsafe_allow_html=True)
