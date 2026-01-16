import streamlit as st
import random
import time
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from kiwipiepy import Kiwi

# ==========================================
# [Backend] 구글 시트 연동 관리자 (최신 주소 적용)
# ==========================================
class GoogleSheetManager:
    def __init__(self):
        try:
            # 1. 최신 Scope 주소로 업데이트 (200 에러 방지)
            scope = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
            
            # 2. Secrets에서 키 가져오기
            if "gcp_service_account" in st.secrets:
                creds_dict = dict(st.secrets["gcp_service_account"])
            else:
                st.error("Secrets 설정 오류: [gcp_service_account] 섹션을 찾을 수 없습니다.")
                st.stop()
                
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            self.client = gspread.authorize(creds)
            
            # 3. 시트 연결 (이름 확인 필수!)
            self.sheet = self.client.open("memory_game_db")
            
            try: self.users_ws = self.sheet.worksheet("users")
            except: self.users_ws = self.sheet.add_worksheet("users", 100, 10); self.users_ws.append_row(["user_id", "password", "level", "xp", "title"])
            
            try: self.collections_ws = self.sheet.worksheet("collections")
            except: self.collections_ws = self.sheet.add_worksheet("collections", 100, 10); self.collections_ws.append_row(["user_id", "card_text", "grade", "collected_at"])
            
        except Exception as e:
            st.error(f"⚠️ 구글 시트 연결 실패! \n원인: {e}\n(해결책: 시트 이름이 'memory_game_db'인지, game-bot 이메일에 '편집자' 공유를 했는지 확인하세요.)")
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
        # 가챠 확률
        rand = random.random()
        if rand < 0.05: grade = "LEGEND"
        elif rand < 0.20: grade = "RARE"
        else: grade = "NORMAL"
        
        # 경험치 계산
        xp_gain = 50 if grade == "LEGEND" else 30 if grade == "RARE" else 10
        new_xp = current_xp + xp_gain
        new_level = current_level
        req_xp = current_level * 100
        
        is_levelup = False
        if new_xp >= req_xp:
            new_level += 1
            new_xp -= req_xp
            is_levelup = True
            
        # 구글 시트 업데이트
        self.users_ws.update_cell(row_idx, 3, new_level)
        self.users_ws.update_cell(row_idx, 4, new_xp)
        self.collections_ws.append_row([user_id, card_text, grade, str(time.strftime('%Y-%m-%d'))])
        
        return grade, is_levelup, xp_gain, new_level, new_xp

    def get_collections(self, user_id):
        all_cards = self.collections_ws.get_all_records()
        # 내 카드만 필터링하고 최신순으로 뒤집기
        my_cards = [c for c in all_cards if str(c['user_id']) == str(user_id)]
        return my_cards[::-1]

# ==========================================
# [UI/UX] 게임 스타일 (귀여운 테마)
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
# [Main] 앱 실행 로직
# ==========================================
st.set_page_config(page_title="메모리 가디언즈", page_icon="🛡️", layout="centered")
apply_game_style()

@st.cache_resource
def load_kiwi(): return Kiwi()

# DB 연결
gm = GoogleSheetManager()

# 세션 초기화
if 'user_id' not in st.session_state:
    st.session_state.user_id = None
    st.session_state.user_row_idx = None
    st.session_state.level = 1
    st.session_state.xp = 0
    if 'page' not in st.session_state: st.session_state.page = 'main'

# 1. 로그인 화면
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
            else: st.error("아이디 또는 비밀번호가 틀렸습니다.")
    with tab2:
        rid = st.text_input("새 아이디")
        rpw = st.text_input("새 비밀번호", type="password")
        if st.button("가입하기"):
            if gm.register(rid, rpw): st.success("가입 완료! 로그인 탭에서 로그인하세요.")
            else: st.error("이미 존재하는 아이디입니다.")

# 2. 로비 화면
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

# 3. 던전 화면 (버그 수정 완료: 정답 고정)
elif st.session_state.page == 'dungeon':
    if st.button("🏠 로비로"): st.session_state.page = 'main'; st.rerun()
    st.header("💀 지식의 던전")
    
    uploaded = st.file_uploader("던전 입장권(.txt)", type=['txt'])
    if uploaded:
        txt = uploaded.getvalue().decode('utf-8')
        kiwi = load_kiwi()
        
        # 파일이 처음 로드되거나, 사용자가 리셋을 원할 때
        if 'sents' not in st.session_state or st.button("🔄 새 던전 생성"):
             st.session_state.sents = [s.text for s in kiwi.split_into_sents(txt) if len(s.text)>5]
             st.session_state.q_idx = 0
             if 'curr_ans' in st.session_state: del st.session_state.curr_ans # 기존 문제 삭제
        
        if st.session_state.sents:
            # [중요] 이미 출제된 문제(curr_ans)가 없으면 새로 만든다
            if 'curr_ans' not in st.session_state:
                curr_sent = st.session_state.sents[st.session_state.q_idx % len(st.session_state.sents)]
                tokens = kiwi.tokenize(curr_sent)
                nouns = [t.form for t in tokens if t.tag.startswith('N') and len(t.form)>1]
                
                if not nouns: # 명사 없으면 스킵
                    st.session_state.q_idx += 1
                    st.rerun()
                
                target_word = random.choice(nouns)
                
                # 세션에 문제 박제 (새로고침 방지)
                st.session_state.curr_sent = curr_sent
                st.session_state.curr_ans = target_word
                st.session_state.curr_html = curr_sent.replace(target_word, '<span class="blank-space"></span>')
            
            # 저장된 문제 표시
            st.markdown(f"""<div class="quiz-card">{st.session_state.curr_html}</div>""", unsafe_allow_html=True)
            
            with st.form("btl"):
                col_i, col_b = st.columns([3, 1])
                with col_i: inp = st.text_input("정답", placeholder="빈칸 단어", label_visibility="collapsed")
                with col_b: sub = st.form_submit_button("🔥 공격")
                
                if sub:
                    # 저장된 정답과 비교
                    if st.session_state.curr_ans in inp:
                        g, up, gain, nl, nx = gm.process_reward(
                            st.session_state.user_id, 
                            st.session_state.curr_sent, 
                            st.session_state.level, 
                            st.session_state.xp, 
                            st.session_state.user_row_idx
                        )
                        st.session_state.level = nl
                        st.session_state.xp = nx
                        
                        if g=="LEGEND": st.balloons(); st.success(f"👑 전설! (+{gain}XP)")
                        elif g=="RARE": st.success(f"✨ 희귀! (+{gain}XP)")
                        else: st.info(f"🛡️ 일반. (+{gain}XP)")
                        
                        time.sleep(1)
                        # 맞췄으니까 저장된 문제 삭제 (다음 문제 출제 트리거)
                        del st.session_state.curr_ans
                        st.session_state.q_idx += 1
                        st.rerun()
                    else:
                        st.error(f"💥 공격 실패! 정답은 '{st.session_state.curr_ans}' 였습니다!")

# 4. 도감 화면
elif st.session_state.page == 'collection':
    if st.button("🏠 로비로"): st.session_state.page = 'main'; st.rerun()
    st.header("📖 수집 도감")
    cards = gm.get_collections(st.session_state.user_id)
    if not cards: st.info("아직 수집한 카드가 없습니다.")
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
