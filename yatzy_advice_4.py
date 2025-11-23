import pygame, random, sys, requests, textwrap, os
from collections import Counter
import threading

# --- 초기 설정 & 상수 ---
pygame.init()
SCREEN_WIDTH, SCREEN_HEIGHT = 1280, 950
WHITE, BLACK, GRAY, LIGHT_GRAY, RED, GREEN, BLUE, GOLD = (255,255,255),(0,0,0),(200,200,200),(230,230,230),(200,0,0),(0,150,0),(0,0,200),(255,215,0)

# 한글 폰트 설정: Windows 환경의 맑은 고딕을 우선 사용
KOREAN_FONT_PATH = os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "Fonts", "malgun.ttf")
if not os.path.exists(KOREAN_FONT_PATH):
    KOREAN_FONT_PATH = None

# 폰트 크기 재조정
try:
    # F_BIG: 60, F_MED: 40, F_SML: 28, F_TINY: 20
    F_BIG, F_MED, F_SML, F_TINY = (pygame.font.Font(KOREAN_FONT_PATH, s) for s in (60, 40, 28, 20))
    # '총점' 및 'Rolls Left'용 미니 폰트 (F_MINI: 18)
    F_MINI = pygame.font.Font(KOREAN_FONT_PATH, 18)
    # 조언용 초미니 폰트 (F_V_TINY: 14pt로 축소)
    F_V_TINY = pygame.font.Font(KOREAN_FONT_PATH, 14) 
except:
    F_BIG, F_MED, F_SML, F_TINY = (pygame.font.Font(None, s) for s in (60, 40, 28, 20))
    F_MINI = pygame.font.Font(None, 18)
    F_V_TINY = pygame.font.Font(None, 14)


SCORE_CATS = [
    "Aces","Twos","Threes","Fours","Fives","Sixes",
    "3 of a Kind","4 of a Kind","Full House","Small Straight","Large Straight","Yatzy","Chance"
]
UPPER_MAP = {"Aces":1,"Twos":2,"Threes":3,"Fours":4,"Fives":5,"Sixes":6}
SMALL_STRAIGHTS = [{1,2,3,4},{2,3,4,5},{3,4,5,6}]
ADVICE_DELAY, ADVICE_INTERVAL = 5000, 10000
SCREEN = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Yatzy Game")

# --- 유틸 ---
def draw_text(txt, font, color, surf, x, y, center=False):
    # 한글 렌더링을 위해 기본 폰트 설정을 KOREAN_FONT_PATH로 변경함
    img = font.render(txt, True, color)
    rect = img.get_rect(center=(x,y) if center else (x,y))
    if not center: rect.topleft = (x,y)
    surf.blit(img, rect)

def draw_dice_face(surf, val, rect):
    if val not in range(1,7): return
    cx, cy, off = rect.centerx, rect.centery, rect.w//4
    patterns = {
        1:[(cx,cy)],
        2:[(cx-off,cy-off),(cx+off,cy+off)],
        3:[(cx-off,cy-off),(cx,cy),(cx+off,cy+off)],
        4:[(cx-off,cy-off),(cx+off,cy-off),(cx-off,cy+off),(cx+off,cy+off)],
        5:[(cx-off,cy-off),(cx+off,cy-off),(cx,cy),(cx-off,cy+off),(cx+off,cy+off)],
        6:[(cx-off,cy-off),(cx+off,cy-off),(cx-off,cy),(cx+off,cy),(cx-off,cy+off),(cx+off,cy+off)]
    }
    for p in patterns[val]: pygame.draw.circle(surf, BLACK, p, 6)

# --- 점수 계산 ---
def calc_score(cat, dice):
    cnt = Counter(dice)
    sset, ssum = set(dice), sum(dice)
    if cat in UPPER_MAP: return sum(d for d in dice if d==UPPER_MAP[cat])
    if cat == "3 of a Kind" and any(c>=3 for c in cnt.values()): return ssum
    if cat == "4 of a Kind" and any(c>=4 for c in cnt.values()): return ssum
    if cat == "Full House" and sorted(cnt.values()) == [2,3]: return 25
    if cat == "Small Straight" and any(st.issubset(sset) for st in SMALL_STRAIGHTS): return 30
    if cat == "Large Straight" and sorted(dice) in ([1,2,3,4,5],[2,3,4,5,6]): return 40
    if cat == "Yatzy" and len(cnt)==1 and dice[0]!=0: return 50
    if cat == "Chance": return ssum
    return 0

# --- API (비동기 처리 함수) ---
def fetch_advice_async(game_instance):
    game_instance.advice_loading = True
    try:
        r = requests.get("https://api.adviceslip.com/advice", timeout=3)
        r.raise_for_status()
        result = r.json()['slip']['advice']
    except Exception:
        result = "Time to make a move! (Network or Data Error)"

    game_instance.advice_future = result
    game_instance.advice_loading = False

# --- UI 위젯 ---
class Button:
    def __init__(self, rect, text, color, hover):
        self.rect = pygame.Rect(rect); self.text=text; self.color=color; self.hover=hover; self.is_hovered=False
    def draw(self, surf):
        pygame.draw.rect(surf, self.hover if self.is_hovered else self.color, self.rect, border_radius=10)
        draw_text(self.text, F_SML, WHITE, surf, self.rect.centerx, self.rect.centery, center=True)
    def check(self, pos): self.is_hovered = self.rect.collidepoint(pos)
    def clicked(self, e): return e.type==pygame.MOUSEBUTTONDOWN and e.button==1 and self.is_hovered

class Player:
    def __init__(self, name):
        self.name=name; self.scores={c:None for c in SCORE_CATS}; self.reset_turn()
        
    def get_upper(self): return sum(v for k,v in self.scores.items() if k in UPPER_MAP and v is not None)
    
    # 35점 Yatzy 보너스 규칙: Upper Section 63점 이상 시 35점 부여
    def bonus(self): return 35 if self.get_upper()>=63 else 0
    
    def total(self): return sum(v for v in self.scores.values() if v is not None)+self.bonus()
    def reset_turn(self): self.dice=[0]*5; self.held=[False]*5; self.rolls=3
    def roll(self):
        if self.rolls<=0: return False
        self.rolls-=1
        for i in range(5):
            if not self.held[i]: self.dice[i]=random.randint(1,6)
        return True

# --- 게임 ---
class Game:
    def __init__(self):
        self.clock=pygame.time.Clock(); self.mouse=(0,0)
        self.buttons={
            k:Button(r,t,c,h) for k,(r,t,c,h) in {
                "1p":((SCREEN_WIDTH//2-100, 300, 200, 60), "1인 플레이", GREEN, (0, 200, 0)),
                "2p":((SCREEN_WIDTH//2-100, 400, 200, 60), "2인 플레이", BLUE, (50, 50, 255)),
                "roll":((SCREEN_WIDTH//2-75,SCREEN_HEIGHT-100,150,50),"ROLL",GREEN,(0,200,0)),
                "quit_ingame":((SCREEN_WIDTH-170,20,150,50),"QUIT",RED,(255,50,50)),
                "restart":((SCREEN_WIDTH-170,80,150,50),"RESTART",RED,(255,50,50)),
                "start":((SCREEN_WIDTH//2-100,600,200,60),"게임 시작",BLUE,(50,50,255)),
                "how_to_play":((SCREEN_WIDTH//2-100, 680, 200, 60), "게임 방법", BLUE, (50, 50, 255)),
                "back_to_menu":((50, 50, 150, 50), "뒤로가기", RED, (255, 50, 50)),
                "play_again":((SCREEN_WIDTH//2-100,500,200,60),"다시 플레이",GREEN,(0,200,0)),
                "quit":((SCREEN_WIDTH//2-100,580,200,60),"종료",RED,(255,50,50)),
            }.items()
        }
        self.reset()

    # 상태 관리
    def reset(self):
        self.num_players = 0
        self.names=[]
        self.players=[]
        self.turn=0
        self.state="MODE_SELECTION" # 초기 상태: 모드 선택
        self.active_input = -1 
        self.caret_visible = False # 텍스트 입력 캐럿
        self.caret_timer = 0
        self.advice=None
        self.advice_on=False
        self.turn_t=pygame.time.get_ticks()
        self.advice_t=0
        
        self.advice_loading = False 
        self.advice_future = None    
        
    def _setup_players(self):
        self.names = [f"플레이어 {i+1}" for i in range(self.num_players)]
        self.players = [Player(n) for n in self.names]
        self.active_input = 0 # 이름 입력 시 첫 번째 플레이어 활성화

    # 이벤트
    def handle_events(self):
        for e in pygame.event.get():
            if e.type==pygame.QUIT or (self.state=="GAME_OVER" and self.buttons["quit"].clicked(e)): return False
            getattr(self, f"ev_{self.state.lower()}")(e)
        return True

    def ev_mode_selection(self, e):
        if e.type == pygame.MOUSEBUTTONDOWN:
            if self.buttons["1p"].clicked(e):
                self.num_players = 1
                self.state = "NAME_INPUT"
                self._setup_players()
            elif self.buttons["2p"].clicked(e):
                self.num_players = 2
                self.state = "NAME_INPUT"
                self._setup_players()
            elif self.buttons["how_to_play"].clicked(e):
                self.state = "HOW_TO_PLAY"


    def ev_name_input(self, e):
        # 입력 상자 위치 계산
        input_rects = []
        total_height = self.num_players * 150
        start_y = (SCREEN_HEIGHT - total_height) // 2
        for i in range(self.num_players):
            y_pos = start_y + i * 150
            input_rects.append(pygame.Rect(SCREEN_WIDTH//2 - 250, y_pos, 500, 50))

        if e.type == pygame.MOUSEBUTTONDOWN:
            clicked_on_input = False
            for i, r in enumerate(input_rects):
                if r.collidepoint(e.pos):
                    self.active_input = i
                    pygame.key.set_text_input_rect(r)
                    pygame.key.start_text_input()
                    clicked_on_input = True
                    break
            if not clicked_on_input and self.active_input != -1:
                self.active_input = -1
                pygame.key.stop_text_input()
            
            if self.buttons["start"].clicked(e):
                for i in range(self.num_players):
                    self.players[i].name = self.names[i].strip() or f"플레이어 {i+1}"
                self.state = "PLAYING"
                self.turn_t = pygame.time.get_ticks()
                if self.active_input != -1: pygame.key.stop_text_input()
            elif self.buttons["how_to_play"].clicked(e):
                self.state = "HOW_TO_PLAY"
                if self.active_input != -1: pygame.key.stop_text_input()
                
        if e.type == pygame.KEYDOWN and self.active_input != -1:
            if e.key == pygame.K_BACKSPACE:
                self.names[self.active_input] = self.names[self.active_input][:-1]
            elif e.key == pygame.K_TAB:
                # TAB 키로 다음 입력 창으로 이동
                if self.num_players > 1:
                    new_active = (self.active_input + 1) % self.num_players
                    self.active_input = new_active
                    pygame.key.set_text_input_rect(input_rects[new_active])
            
        # 한글 입력 처리를 위해 TEXTINPUT 이벤트 사용
        if e.type == pygame.TEXTINPUT and self.active_input != -1:
            if len(self.names[self.active_input]) < 15:
                 self.names[self.active_input] += e.text

    def ev_how_to_play(self, e):
        if self.buttons["back_to_menu"].clicked(e):
            self.state = "MODE_SELECTION" # 이름 입력 대신 모드 선택으로 돌아가게 수정

    def ev_playing(self, e):
        cur=self.players[self.turn]
        if self.buttons["roll"].clicked(e) and cur.roll():
            self.advice_on=True; self.advice = None; now=pygame.time.get_ticks()
            self.turn_t=now; self.advice_t=now-ADVICE_INTERVAL
        elif self.buttons["quit_ingame"].clicked(e): pygame.event.post(pygame.event.Event(pygame.QUIT))
        elif self.buttons["restart"].clicked(e): self.reset()
        elif e.type==pygame.MOUSEBUTTONDOWN and e.button==1:
            self.click_dice(cur); self.click_score(cur)

    def ev_game_over(self, e):
        if self.buttons["play_again"].clicked(e): self.reset()

    # 클릭 로직
    def click_dice(self, cur):
        if cur.rolls==3: return

        is_single_player = self.num_players == 1
        panel_width = SCREEN_WIDTH if is_single_player else SCREEN_WIDTH // 2
        x0 = 0 if is_single_player else (SCREEN_WIDTH // 2) * self.turn

        # 주사위 위치 계산 로직 (기존 2P와 유사한 간격 유지)
        DICE_SIZE = 80
        DICE_START_OFFSET = 80 # 원래 x0 + 80
        DICE_SPACING = 100
        
        # 1인 모드 시 주사위 행을 중앙에 배치
        if is_single_player:
            DICE_ROW_WIDTH = DICE_SPACING * 4 + DICE_SIZE
            start_dice_x = x0 + (panel_width - DICE_ROW_WIDTH) // 2
        else:
            start_dice_x = x0 + DICE_START_OFFSET

        for i in range(5):
            # 주사위 Y 위치: 10픽셀 더 위로 조정 (SCREEN_HEIGHT - 190)
            r = pygame.Rect(start_dice_x + i * DICE_SPACING, SCREEN_HEIGHT - 190, DICE_SIZE, DICE_SIZE)
            if r.collidepoint(self.mouse):
                cur.held[i] ^= True

    def click_score(self, cur):
        if cur.rolls==3: return
        
        is_single_player = self.num_players == 1
        panel_width = SCREEN_WIDTH if is_single_player else SCREEN_WIDTH // 2
        x0 = 0 if is_single_player else (SCREEN_WIDTH // 2) * self.turn
        
        # 원본 파일 (yatzy_advice_3_수정 전.py) 기준 y0=220, h=35
        y0, h = 220, 35
        y_upper_end = y0 + 6 * h
        for i,cat in enumerate(SCORE_CATS):
            # 원본 파일 기준 y 계산 로직
            y = y0+i*h if i<6 else y_upper_end+70+(i-6)*h 
            
            # 카테고리 호버/클릭 영역 조정 (y-5 -> y-4로 조정하여 1픽셀 더 아래로 이동)
            r=pygame.Rect(x0+40, y+2, panel_width-80, h)
            
            if cur.scores[cat] is None and r.collidepoint(self.mouse):
                is_yat = len(set(cur.dice))==1 and cur.dice[0]!=0
                
                if cat == "Yatzy" and is_yat:
                    cur.scores[cat] = 50
                else:
                    cur.scores[cat] = calc_score(cat, cur.dice)
                    
                cur.dice=[0]*5
                
                self.turn = (self.turn + 1) % self.num_players
                self.players[self.turn].reset_turn()
                self.turn_t=pygame.time.get_ticks()
                self.advice_on=False
                self.advice=None
                
                if all(p.scores[c] is not None for p in self.players for c in SCORE_CATS): 
                    self.state="GAME_OVER"
                break

    # 업데이트 & 렌더
    def update(self):
        self.mouse=pygame.mouse.get_pos()
        for b in self.buttons.values(): b.check(self.mouse)
        now=pygame.time.get_ticks()

        # Caret blinking 로직
        if self.active_input != -1:
            if now - self.caret_timer > 500:
                self.caret_timer = now
                self.caret_visible = not self.caret_visible
            pygame.key.start_text_input()
        else:
             pygame.key.stop_text_input()
        
        # 비동기 API 호출 시작 로직
        if self.state=="PLAYING" and self.advice_on and not self.advice_loading and \
           now-self.turn_t>=ADVICE_DELAY and now-self.advice_t>=ADVICE_INTERVAL:
            
            threading.Thread(target=fetch_advice_async, args=(self,)).start()
            self.advice_t=now
            
        # 비동기 API 호출 완료 결과 처리
        if self.advice_future is not None:
            self.advice = self.advice_future
            self.advice_future = None

    def draw(self):
        # 상태에 따라 다른 draw 함수 호출
        if self.state == "MODE_SELECTION":
            self.draw_mode_selection()
        elif self.state == "NAME_INPUT":
            self.draw_name_input()
        elif self.state == "HOW_TO_PLAY":
            self.draw_how_to_play()
        elif self.state == "PLAYING":
            self.draw_playing()
        elif self.state == "GAME_OVER":
            self.draw_game_over()
            
        pygame.display.flip()

    def draw_mode_selection(self):
        SCREEN.fill(WHITE)
        draw_text("Yatzy Game", F_BIG, BLACK, SCREEN, SCREEN_WIDTH // 2, 150, True)
        draw_text("플레이 모드 선택", F_MED, BLACK, SCREEN, SCREEN_WIDTH // 2, 220, True)
        self.buttons["1p"].draw(SCREEN)
        self.buttons["2p"].draw(SCREEN)
        self.buttons["how_to_play"].draw(SCREEN)

    def draw_name_input(self):
        SCREEN.fill(WHITE)
        draw_text(f"플레이어 이름 입력 ({self.num_players}인 모드)", F_BIG, BLACK, SCREEN, SCREEN_WIDTH//2, 100, True)

        total_height = self.num_players * 150
        start_y = (SCREEN_HEIGHT - total_height) // 2

        for i, name in enumerate(self.names):
            y_pos = start_y + i * 150
            draw_text(f"플레이어 {i+1}:", F_MED, BLACK, SCREEN, SCREEN_WIDTH//2, y_pos - 50, True)
            r = pygame.Rect(SCREEN_WIDTH//2 - 250, y_pos, 500, 50)
            
            # Draw input box
            pygame.draw.rect(SCREEN, LIGHT_GRAY, r)
            pygame.draw.rect(SCREEN, BLACK if self.active_input == i else GRAY, r, 2)

            # Draw text
            text_surf = F_SML.render(name, True, BLACK)
            SCREEN.blit(text_surf, (r.x + 10, r.y + 10))

            # Draw caret
            if self.active_input == i and self.caret_visible:
                text_width = F_SML.size(name)[0]
                caret_pos_x = r.x + 10 + text_width
                pygame.draw.line(SCREEN, BLACK, (caret_pos_x, r.y + 12), (caret_pos_x, r.y + r.height - 12), 2)

        self.buttons["start"].draw(SCREEN)
        self.buttons["how_to_play"].draw(SCREEN)

    def draw_how_to_play(self):
        SCREEN.fill(WHITE)
        rules = [
            "**[Yatzy 게임 방법 및 규칙]**",
            "",
            "**1. 목표:** 13개의 카테고리에 점수를 모두 채워 가장 높은 총점을 얻는 것입니다.",
            "",
            "**2. 게임 진행:**",
            " - 자기 턴이 되면 'ROLL' 버튼을 눌러 주사위 5개를 굴립니다.",
            " - 한 턴에 **최대 3번**까지 굴릴 수 있습니다. (굴린 횟수 표시됨)",
            " - 굴린 후, 원하는 주사위를 클릭하여 '고정'(Held)하거나 고정을 풀 수 있습니다.",
            " - 3번의 기회를 모두 사용했거나, 중간에 멈추고 싶다면 점수판에서 점수를 기록할 카테고리 하나를 선택해야 합니다.",
            " - 점수를 기록하면 턴이 상대방에게 넘어갑니다.",
            "",
            "**3. 점수 계산 (주요 카테고리):**",
            " - **Aces ~ Sixes:** 선택한 숫자의 눈금을 모두 더한 값.",
            " - **Upper Bonus:** Aces~Sixes 합계가 **63점 이상**일 경우 **35점** 추가.",
            " - **Full House:** 동일한 주사위 3개와 2개. 고정 25점.",
            " - **Small Straight:** 4개의 연속된 숫자 (예: 1-2-3-4). 고정 30점.",
            " - **Large Straight:** 5개의 연속된 숫자 (예: 1-2-3-4-5). 고정 40점.",
            " - **Yatzy:** 5개 주사위가 모두 동일한 숫자. 고정 50점.",
            "",
            "**4. 승리 조건:**",
            "모든 플레이어가 13개 카테고리를 모두 채웠을 때, 총점이 더 높은 플레이어가 승리합니다.",
            "",
            "**플레이 팁:**",
            "어떤 카테고리를 선택할지 고민된다면, 당신의 이름 아래에 나타나는 조언을 참고하세요!",
        ]

        draw_text("Yatzy 게임 방법", F_BIG, BLACK, SCREEN, SCREEN_WIDTH // 2, 40, True) # 제목 Y 위치 상향

        # 텍스트가 잘리지 않도록 F_TINY(20)보다 작은 F_MINI(18) 사용
        line_height = F_MINI.get_height() + 5 
        start_y = 100 # 시작 Y 위치 상향
        x_start = 80
        
        for i, line in enumerate(rules):
            font = F_TINY if line.startswith("**") else F_MINI # 소제목 F_TINY(20), 본문 F_MINI(18)
            
            display_line = line.replace('**', '') 

            wrapped_lines = textwrap.wrap(display_line, width=130) # 줄바꿈 폭을 최대로 늘림
            
            for j, wrapped_line in enumerate(wrapped_lines):
                # 목록의 경우 들여쓰기 적용
                x_pos = x_start + (20 if wrapped_line.strip().startswith("-") else 0)
                draw_text(wrapped_line, font, BLACK, SCREEN, x_pos, start_y, center=False)
                start_y += font.get_height() + 2 # 줄 간격
            
            if not wrapped_lines:
                start_y += F_TINY.get_height() # 빈 줄 처리 (빈 줄도 간격 확보)
            else:
                start_y += 5 # 섹션 간격 조정 (약간의 추가 공간)


        self.buttons["back_to_menu"].draw(SCREEN)

    def draw_playing(self):
        SCREEN.fill(WHITE)
        cur = self.players[self.turn]
        is_single_player = self.num_players == 1

        if not is_single_player:
            # 2P 모드 (원본 레이아웃 유지)
            pygame.draw.line(SCREEN, GRAY, (SCREEN_WIDTH // 2, 0), (SCREEN_WIDTH // 2, SCREEN_HEIGHT), 4)
            self.draw_player(self.players[0], 0, is_single_player=False)
            self.draw_player(self.players[1], SCREEN_WIDTH // 2, is_single_player=False)
        else:
            # 1P 모드 (2P 패널 폭을 중앙에 배치)
            x_offset = SCREEN_WIDTH // 4 
            self.draw_player(cur, x_offset, is_single_player=True)

        # Rolls Left 텍스트 위치: 원본 (SCREEN_HEIGHT - 30) 근처로 복구하되, 아래로 살짝 내림
        roll_text_y = SCREEN_HEIGHT - 30 
        
        # 굴린 횟수 표시 상세화 (요청 사항 반영)
        roll_text = f"ROLLS LEFT: {cur.rolls} (굴린 횟수: {3-cur.rolls}회)"
        
        # 텍스트 크기 F_MINI로 축소
        roll_font = F_MINI 

        # 2P 모드에서는 현재 플레이어 패널 중앙에 표시 (원본과 유사하게)
        x = SCREEN_WIDTH//4 + (SCREEN_WIDTH//2)*self.turn
        draw_text(roll_text, roll_font, BLACK, SCREEN, x, roll_text_y, True)
            
        # ROLL 버튼을 더 아래로 내림 (SCREEN_HEIGHT - 70)
        self.buttons['roll'].rect.centerx = SCREEN_WIDTH // 2
        self.buttons['roll'].rect.centery = SCREEN_HEIGHT - 70


        for k in ("roll", "quit_ingame", "restart"):
            self.buttons[k].draw(SCREEN)

    def draw_player(self, p, x0, is_single_player=False):
        # 1인 모드 시 패널 폭을 2P 폭(SCREEN_WIDTH // 2)으로 고정
        panel_width = SCREEN_WIDTH // 2
        is_cur = (p is self.players[self.turn])
        
        # --- 레이아웃 변수 (원본 파일과 유사하도록 조정) ---
        name_y = 50 
        total_score_label_y = 100
        total_score_y = 150
        advice_y = 185 # 원본 advice 위치
        board_y = 220 # 원본 score board 시작 Y (y0)
        
        name_x = x0 + panel_width // 2
        
        # Draw Name (현재 턴 표시)
        if is_cur:
            w,h = F_MED.size(p.name)
            pygame.draw.rect(SCREEN, GOLD, (name_x-w//2-10, name_y-h//2-5, w+20, h+10), border_radius=5)
        draw_text(p.name, F_MED, BLACK, SCREEN, name_x, name_y, True)
        
        # Draw Total Score
        draw_text("Total Score", F_SML, BLACK, SCREEN, name_x, total_score_label_y, True) # 총점 F_MINI로 축소
        draw_text(str(p.total()), F_BIG, BLUE, SCREEN, name_x, total_score_y, True)
        
        # Draw Advice
        if is_cur and self.advice_on:
            advice_wrap_width = 40
            if self.advice_loading:
                draw_text("조언 로딩 중...", F_V_TINY, GRAY, SCREEN, x0 + 50, advice_y) # F_V_TINY
            elif self.advice:
                lines = textwrap.wrap(self.advice, width=advice_wrap_width)
                for i,line in enumerate(lines):
                    if i < 2: # 조언은 최대 2줄만 표시
                        draw_text(line, F_V_TINY, RED, SCREEN, x0 + 50, advice_y + i*(F_V_TINY.get_height()+2)) # F_V_TINY
                    else:
                        break
                        
        # Draw Scoreboard
        y0,h = board_y, 35 # 원본 높이 35 사용
        y_upper_end=y0+6*h
        
        score_name_x = x0 + 50
        score_value_x = x0 + panel_width - 50
        
        for i,cat in enumerate(SCORE_CATS):
            # 원본 y 계산 로직 사용
            y = y0+i*h if i<6 else y_upper_end+70+(i-6)*h 
            
            # 카테고리 호버 영역 (y-10 -> y-4로 조정하여 6픽셀 아래로 이동)
            r=pygame.Rect(x0+40, y+2, panel_width-80, h)
            
            if i==6: pygame.draw.line(SCREEN, GRAY, (x0+40, y_upper_end+70-10), (x0+panel_width-40, y_upper_end+70-10), 2)
            
            selectable = is_cur and p.scores[cat] is None and p.rolls<3
            hovered = r.collidepoint(self.mouse)
            
            if selectable and hovered: pygame.draw.rect(SCREEN, LIGHT_GRAY, r, border_radius=5)
            
            draw_text(cat, F_SML, BLUE if selectable and hovered else BLACK, SCREEN, score_name_x, y) # F_SML
            
            if p.scores[cat] is not None:
                # 점수 우측 정렬 (F_SML)
                draw_text(str(p.scores[cat]), F_SML, BLACK, SCREEN, score_value_x - F_SML.size(str(p.scores[cat]))[0], y)
            elif selectable:
                is_yat = len(set(p.dice))==1 and p.dice[0]!=0
                pts = 50 if cat == "Yatzy" and is_yat else calc_score(cat, p.dice) 
                # 점수 우측 정렬 (F_SML)
                draw_text(str(pts), F_SML, BLUE if hovered else GREEN, SCREEN, score_value_x - F_SML.size(str(pts))[0], y)
        
        # Draw Upper Total & Bonus
        draw_text(f"Upper Total: {p.get_upper()} / 63", F_TINY, BLACK, SCREEN, x0+50, y_upper_end+10)
        
        # 보너스 우측 정렬 (F_TINY)
        bonus_text = f"Bonus: {p.bonus()}"
        draw_text(bonus_text, F_TINY, GOLD if p.bonus()>0 else BLACK, SCREEN, score_value_x - F_TINY.size(bonus_text)[0], y_upper_end + 35)
        
        # Draw Dice
        # 주사위 Y 위치 조정 (170)
        dice_y = SCREEN_HEIGHT-190 # 10픽셀 더 위로
        if any(d>0 for d in p.dice):
            DICE_SIZE = 80
            DICE_SPACING = 100

            if is_single_player:
                DICE_ROW_WIDTH = DICE_SPACING * 4 + DICE_SIZE
                start_dice_x = x0 + (panel_width - DICE_ROW_WIDTH) // 2
            else:
                start_dice_x = x0 + 80 # 2P 모드는 원래처럼 고정 오프셋 (x0 + 80)

            for i,val in enumerate(p.dice):
                r=pygame.Rect(start_dice_x + i*DICE_SPACING, dice_y, DICE_SIZE, DICE_SIZE) 
                pygame.draw.rect(SCREEN, BLACK, r, 2, border_radius=10)
                draw_dice_face(SCREEN, val, r)
                if p.held[i]: pygame.draw.rect(SCREEN, RED, r, 4, border_radius=10)

    def draw_game_over(self):
        self.draw_playing(); self._overlay(220)
        
        if self.num_players == 1:
            s1 = self.players[0].total()
            winner = f"최종 점수: {s1}점"
            score_text = ""
        else:
            s1,s2 = self.players[0].total(), self.players[1].total()
            winner = f"{self.players[0].name} 승리!" if s1>s2 else f"{self.players[1].name} 승리!" if s2>s1 else "무승부!"
            score_text = f"{self.players[0].name}: {s1} vs {self.players[1].name}: {s2}"

        draw_text("게임 종료", F_BIG, GOLD, SCREEN, SCREEN_WIDTH//2, 200, True)
        draw_text(winner, F_MED, WHITE, SCREEN, SCREEN_WIDTH//2, 300, True)
        if score_text:
            draw_text(score_text, F_SML, GRAY, SCREEN, SCREEN_WIDTH//2, 360, True)
        self.buttons["play_again"].draw(SCREEN); self.buttons["quit"].draw(SCREEN)

    def _overlay(self, alpha):
        ov=pygame.Surface((SCREEN_WIDTH,SCREEN_HEIGHT), pygame.SRCALPHA)
        ov.fill((0,0,0,alpha)); SCREEN.blit(ov,(0,0))

    # 루프
    def run(self):
        running=True
        while running:
            running=self.handle_events(); self.update(); self.draw(); self.clock.tick(60)
        pygame.quit(); sys.exit()

if __name__ == '__main__':
    Game().run()