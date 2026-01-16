import streamlit as st
import random
import time
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from kiwipiepy import Kiwi

# ==========================================
# [Backend] 구글 시트 연동 관리자
# ==========================================
class GoogleSheetManager:
    def __init__(self):
        try:
            # Secrets에서 키 가져오기
            scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
            # secrets에 json 내용을 통째로 넣었을 경우를 대비한 처리
            if "gcp_service_account" in st.secrets:
                creds_dict = dict(st.secrets["gcp_service_account"])
            else:
                # 만약 toml 형식이 아니라면 에러가 날 수 있음
                st.error("Secrets 설정 오류: [gcp_service_account] 섹션을 찾을 수 없습니다.")
                st.stop()
                
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            self.client = gspread.authorize(creds)
            
            # 시트 연결 (시트 이름이 'memory_game_db'여야 함)
            self.sheet = self.client.open("memory_game_db")
            
            try: self.users_ws = self.sheet.worksheet("users")
            except: self.users_ws = self.sheet.add_worksheet("users", 100, 10); self.users_ws.append_row(["user_id", "password", "level", "xp", "title"])
            
            try: self.collections_ws = self.sheet.worksheet("collections")
            except: self.collections_ws = self.sheet.add_worksheet("collections", 100, 10); self.collections_ws.append_row(["user_id", "card_text", "grade", "collected_at"])
            
        except Exception as e:
            st.error(f"구글 연결 실패! (시트 이름이 'memory_game_db' 인가요? 공유는 하셨나요?) 에러: {e}")
            st.stop()

    def login(self, user_id, password):
        records = self.users_ws.get_all_records()
        for i, row in enumerate(records):
            if str(row['user_id']) == str(user_id) and str(row['password']) == str(password):
                return row, i + 2
        return None, None

    def register(self, user_id, password):
        records = self.users_ws.get_all_records()
        for row in records:
            if str(row['user_id']) == str(user_id): return False
        self.users_ws.append_row([user_id, password, 1, 0, "견습 가디언"])
        return True

    def process_reward(self, user_id, card_text, current_level, current_xp, row_idx):
        rand = random.random()
        if rand < 0.05: grade = "LEGEND"
        elif rand < 0.20: grade = "RARE"
        else: grade = "NORMAL"
        
        xp_gain = 50 if grade == "LEGEND" else 30 if grade == "RARE" else 10
        new_xp = current_xp + xp_gain
        new_level = current_level
        req_xp = current_level * 100
        
        is_levelup = False
        if new_xp >= req_xp:
            new_level += 1
            new_xp -= req_xp
            is_levelup = True
            
        self.users_ws.update_cell(row_idx, 3, new_level)
        self.users_ws.update_cell(row_idx, 4, new_xp)
        self.collections_ws.append_row([user_id, card_text, grade, str(time.strftime('%Y-%m-%d'))])
        
        return grade, is_levelup, xp_gain, new_level, new_xp

    def get_collections(self, user_id):
        all_cards = self.collections_ws.get_all_records()
        return [c for c in all_cards if str(c['user_id']) == str(user_id)]

# ==========================================
# [UI/UX] 게임 스타일 (귀여운 버전)
# ==========================================
def apply_game_style():
    st.markdown("""
        <link href="https://fonts.googleapis.com/css2?family=Jua&display=swap" rel="stylesheet">
        <style>
        .stApp { background: linear-gradient(to bottom, #1a1a2e, #16213e, #0f3460); color: #ffffff; font-family: 'Jua', sans-serif; }
        .main-avatar-container { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 30px 0; }
        .avatar-emoji { font-size: 120px; filter: drop-shadow(0 0 15px rgba(255,215,0,0.5)); animation: float 3s ease-in-out infinite; }
        .user-info-box { background: rgba(0,0,0,0.5); padding: 10px 20px; border-radius: 20px; margin-top: -20px; border: 2px solid #FFD700; }
        .level-text { font-size: 1.5rem; color: #FFD700; }
        .stProgress > div > div > div > div { background: linear-gradient(to right, #00b09b, #96c93d); }
        .stButton > button { width: 100%; height: 60px; border-radius: 15px; border: none; font-size: 1.2rem; font-family: 'Jua', sans-serif; transition: all 0.2s; color: white; }
        div[data-testid="column"]:nth-of-type(1) .stButton > button { background: linear-gradient(45deg, #FF416C, #FF4B2B); box-shadow: 0 5px 15px rgba(255, 65, 108, 0.4); }
        div[data-testid="column"]:nth-of-type(2) .stButton > button { background: linear-gradient(45deg, #7F7FD5, #86A8E7, #91EAE4); box-shadow: 0 5px 15px rgba(127, 127, 213, 0.4); }
        .stButton > button:hover { transform: scale(1.05); filter: brightness(1.1); }
        .quiz-card { background-color: #fff8dc; border: 4px solid #8b4513; border-radius: 15px; padding: 25px; margin: 20px auto; box-shadow: 0 10px 25px rgba(0,0,0,0.5); color: #3d2b07; font-size: 1.2rem; line-height: 1.6; position: relative; text-align: center; }
        .quiz-card::before { content: "📜 QUEST CARD"; position: absolute; top: -15px; left: 50%; transform: translateX(-50%); background: #8b4513; color: #FFD700; padding: 5px 15px; border-radius: 10px; font-size: 0.9rem; }
        .blank-space { display: inline-block; min-width: 60px; border-bottom: 3px dashed #8b4513; margin: 0 5px; }
        .col-card { padding: 15px; border-radius: 10px; margin-bottom: 10px; color: #000; font-weight: bold; position: relative; overflow: hidden; }
        .grade-badge { position: absolute; top: 0; right: 0; padding: 5px 10px; font-size: 0.8rem; color: white; border-bottom-left-radius: 10px; }
        .card-N { background: #d3cce3; border-left: 5px solid #888; } .card-N .grade-badge { background: #888; }
        .card-R { background: #89f7fe; border-left: 5px solid #0000ff; } .card-R .grade-badge { background: #0000ff; }
        .card-L { background: linear-gradient(45deg, #f2994a, #f2c94c); border-left: 5px solid gold; box-shadow: 0 0 10px gold; } .card-L .grade-badge { background: gold; color: black; }
        @keyframes float { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-15px); } }
        </style>
    """, unsafe_allow_html=True)

# ==========================================
# [Main] 앱 실행
# ==========================================
st.set_page_config(page_title="메모리 가디언즈", page_icon="🛡️", layout="centered")
apply_game_style()

@st.cache_resource
def load_kiwi(): return Kiwi()

# DB 연결 (실패 시 에러 메시지 출력됨)
gm = GoogleSheetManager()

if 'user_id' not in st.session_state:
    st.session_state.user_id = None
    st.session_state.user_row_idx = None
    st.session_state.level = 1
    st.session_state.xp = 0
    if 'page' not in st.session_state: st.session_state.page = 'main'

# 화면 1: 로그인
if st.session_state.user_id is None:
    st.title("🛡️ 메모리 가디언즈")
    st.caption("Google Sheets Online Ver.")
    tab1, tab2 = st.tabs(["로그인", "회원가입"])
    with tab1:
        lid = st.text_input("아이디")
        lpw = st.text_input("비밀번호", type="password")
        if st.button("접속하기", type="primary"):
            user_data, row_idx = gm.login(lid, lpw)
            if user_data:
                st.session_state.user_id = lid
                st.session_state.user_row_idx = row_idx
                st.session_state.level = user_data['level']
                st.session_state.xp = user_data['xp']
                st.rerun()
            else: st.error("정보 불일치")
    with tab2:
        rid = st.text_input("새 아이디")
        rpw = st.text_input("새 비밀번호", type="password")
        if st.button("가입하기"):
            if gm.register(rid, rpw): st.success("가입 완료! 로그인하세요.")
            else: st.error("이미 존재하는 아이디")

# 화면 2: 로비
elif st.session_state.page == 'main':
    u_id, lv, xp = st.session_state.user_id, st.session_state.level, st.session_state.xp
    req_xp = lv * 100
    avatar = "🥚" if lv < 5 else "🐣" if lv < 10 else "🦅" if lv < 20 else "🐲"
    
    col_top1, col_top2 = st.columns([3, 1])
    with col_top2:
        if st.button("로그아웃"):
            st.session_state.user_id = None
            st.rerun()
            
    st.markdown(f"""
        <div class="main-avatar-container">
            <div class="avatar-emoji">{avatar}</div>
            <div class="user-info-box"><span class="level-text">Lv.{lv}</span> {u_id}</div>
        </div>
    """, unsafe_allow_html=True)
    
    st.write(f"**성장 진행도** ({xp} / {req_xp} XP)")
    st.progress(min(xp / req_xp, 1.0))
    st.write(""); st.write("")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("⚔️ 던전 입장"): st.session_state.page = 'dungeon'; st.rerun()
    with col2:
        if st.button("📖 내 도감"): st.session_state.page = 'collection'; st.rerun()

# 화면 3: 던전
elif st.session_state.page == 'dungeon':
    if st.button("🏠 로비로"): st.session_state.page = 'main'; st.rerun()
    st.header("💀 지식의 던전")
    
    uploaded = st.file_uploader("던전 입장권(.txt)", type=['txt'])
    if uploaded:
        txt = uploaded.getvalue().decode('utf-8')
        kiwi = load_kiwi()
        if 'sents' not in st.session_state or st.button("🔄 새 던전 생성"):
             st.session_state.sents = [s.text for s in kiwi.split_into_sents(txt) if len(s.text)>5]
             st.session_state.q_idx = 0
        
        if st.session_state.sents:
            curr = st.session_state.sents[st.session_state.q_idx % len(st.session_state.sents)]
            tokens = kiwi.tokenize(curr)
            nouns = [t.form for t in tokens if t.tag.startswith('N') and len(t.form)>1]
            
            if nouns:
                ans = random.choice(nouns)
                q_html = curr.replace(ans, '<span class="blank-space"></span>')
                
                st.markdown(f"""<div class="quiz-card">{q_html}</div>""", unsafe_allow_html=True)
                
                with st.form("btl"):
                    col_i, col_b = st.columns([3, 1])
                    with col_i: inp = st.text_input("정답", placeholder="빈칸 단어", label_visibility="collapsed")
                    with col_b: sub = st.form_submit_button("🔥 공격")
                    
                    if sub:
                        if ans in inp:
                            g, up, gain, nl, nx = gm.process_reward(st.session_state.user_id, curr, st.session_state.level, st.session_state.xp, st.session_state.user_row_idx)
                            st.session_state.level = nl
                            st.session_state.xp = nx
                            
                            if g=="LEGEND": st.balloons(); st.success(f"👑 전설! (+{gain})")
                            elif g=="RARE": st.success(f"✨ 희귀! (+{gain})")
                            else: st.info(f"🛡️ 일반. (+{gain})")
                            time.sleep(1); st.session_state.q_idx += 1; st.rerun()
                        else: st.error(f"💥 땡! 정답: {ans}")
            else: st.session_state.q_idx += 1; st.rerun()

# 화면 4: 도감
elif st.session_state.page == 'collection':
    if st.button("🏠 로비로"): st.session_state.page = 'main'; st.rerun()
    st.header("📖 수집 도감")
    cards = gm.get_collections(st.session_state.user_id)
    if not cards: st.info("수집 내역이 없습니다.")
    else:
        for c in cards:
            g = c['grade']
            g_s = g[0]
            st.markdown(f"""
                <div class="col-card card-{g_s}">
                    <div class="grade-badge">{g}</div>
                    <div style="margin-top:15px;">{c['card_text']}</div>
                    <div style="font-size:0.8em; opacity:0.6; margin-top:5px;">{c['collected_at']}</div>
                </div>
            """, unsafe_allow_html=True)
