import pygame, random, sys, requests, textwrap
from collections import Counter

# --- 초기 설정 & 상수 ---
pygame.init()
SCREEN_WIDTH, SCREEN_HEIGHT = 1280, 950
WHITE, BLACK, GRAY, LIGHT_GRAY, RED, GREEN, BLUE, GOLD = (255,255,255),(0,0,0),(200,200,200),(230,230,230),(200,0,0),(0,150,0),(0,0,200),(255,215,0)
F_BIG, F_MED, F_SML, F_TINY = (pygame.font.Font(None, s) for s in (72,48,36,24))
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

# --- API ---
def fetch_advice():
    try:
        r = requests.get("https://api.adviceslip.com/advice", timeout=3)
        r.raise_for_status(); return r.json()['slip']['advice']
    except Exception:
        return "Time to make a move! (Network or Data Error)"

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
        self.name=name; self.scores={c:None for c in SCORE_CATS}; self.yatzy_hits=0; self.reset_turn()
    def get_upper(self): return sum(v for k,v in self.scores.items() if k in UPPER_MAP and v is not None)
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
                "roll":((SCREEN_WIDTH//2-75,SCREEN_HEIGHT-100,150,50),"ROLL",GREEN,(0,200,0)),
                "quit_ingame":((SCREEN_WIDTH-170,20,150,50),"QUIT",RED,(255,50,50)),
                "restart":((SCREEN_WIDTH-170,80,150,50),"RESTART",RED,(255,50,50)),
                "start":((SCREEN_WIDTH//2-100,600,200,60),"Start Game",BLUE,(50,50,255)),
                "play_again":((SCREEN_WIDTH//2-100,500,200,60),"Play Again",GREEN,(0,200,0)),
                "quit":((SCREEN_WIDTH//2-100,580,200,60),"Quit",RED,(255,50,50)),
            }.items()
        }
        self.reset()

    # 상태 관리
    def reset(self):
        self.names=["Player 1","Player 2"]; self.players=[Player(n) for n in self.names]
        self.turn=0; self.state="NAME_INPUT"; self.active_input=0
        self.yatzy_flash=-1; self.advice=None; self.advice_on=False
        self.turn_t=pygame.time.get_ticks(); self.advice_t=0
        for p in self.players: p.reset_turn()

    # 이벤트
    def handle_events(self):
        for e in pygame.event.get():
            if e.type==pygame.QUIT or (self.state=="GAME_OVER" and self.buttons["quit"].clicked(e)): return False
            getattr(self, f"ev_{self.state.lower()}")(e)
        return True

    def ev_name_input(self, e):
        p1, p2 = pygame.Rect(SCREEN_WIDTH//2-250,300,500,50), pygame.Rect(SCREEN_WIDTH//2-250,450,500,50)
        if e.type==pygame.MOUSEBUTTONDOWN:
            self.active_input = 0 if p1.collidepoint(e.pos) else 1 if p2.collidepoint(e.pos) else self.active_input
            if self.buttons["start"].clicked(e):
                self.players[0].name=self.names[0] or "Player 1"
                self.players[1].name=self.names[1] or "Player 2"
                self.state="PLAYING"; self.turn_t=pygame.time.get_ticks()
        if e.type==pygame.KEYDOWN:
            if e.key==pygame.K_BACKSPACE: self.names[self.active_input]=self.names[self.active_input][:-1]
            elif e.key==pygame.K_TAB: self.active_input^=1
            elif len(self.names[self.active_input])<15: self.names[self.active_input]+=e.unicode

    def ev_playing(self, e):
        cur=self.players[self.turn]
        if self.buttons["roll"].clicked(e) and cur.roll():
            self.advice_on=True; now=pygame.time.get_ticks()
            self.turn_t=now; self.advice_t=now-ADVICE_INTERVAL  # 즉시 1회 허용
        elif self.buttons["quit_ingame"].clicked(e): pygame.event.post(pygame.event.Event(pygame.QUIT))
        elif self.buttons["restart"].clicked(e): self.reset()
        elif e.type==pygame.MOUSEBUTTONDOWN and e.button==1:
            self.click_dice(cur); self.click_score(cur)

    def ev_game_over(self, e):
        if self.buttons["play_again"].clicked(e): self.reset()

    # 클릭 로직
    def click_dice(self, cur):
        if cur.rolls==3: return
        x0=(SCREEN_WIDTH//2)*self.turn
        for i in range(5):
            r=pygame.Rect(x0+80+i*100, SCREEN_HEIGHT-200, 80,80)
            if r.collidepoint(self.mouse): cur.held[i]^=True

    def click_score(self, cur):
        if cur.rolls==3: return
        x0=(SCREEN_WIDTH//2)*self.turn; y0, h = 220, 35; y_upper_end = y0+6*h
        for i,cat in enumerate(SCORE_CATS):
            y = y0+i*h if i<6 else y_upper_end+70+(i-6)*h
            r=pygame.Rect(x0+40, y-10, SCREEN_WIDTH//2-80, h)
            if cur.scores[cat] is None and r.collidepoint(self.mouse):
                is_yat = len(set(cur.dice))==1 and cur.dice[0]!=0
                is_bonus = is_yat and cur.yatzy_hits>=1
                cur.scores[cat] = 50 if is_yat else calc_score(cat, cur.dice)
                cur.dice=[0]*5
                if is_yat:
                    self.yatzy_flash=self.turn
                    cur.yatzy_hits += 1
                # 턴 변경
                self.turn^=1; self.players[self.turn].reset_turn(); self.turn_t=pygame.time.get_ticks()
                self.advice_on=False; self.advice=None; self.yatzy_flash=-1
                if all(p.scores[c] is not None for p in self.players for c in SCORE_CATS): self.state="GAME_OVER"
                break

    # 업데이트 & 렌더
    def update(self):
        self.mouse=pygame.mouse.get_pos()
        for b in self.buttons.values(): b.check(self.mouse)
        now=pygame.time.get_ticks()
        if self.state=="PLAYING" and self.advice_on and now-self.turn_t>=ADVICE_DELAY and now-self.advice_t>=ADVICE_INTERVAL:
            self.advice=fetch_advice(); self.advice_t=now

    def draw(self):
        getattr(self, f"draw_{self.state.lower()}")(); pygame.display.flip()

    def draw_name_input(self):
        SCREEN.fill(WHITE)
        draw_text("Enter Player Names", F_BIG, BLACK, SCREEN, SCREEN_WIDTH//2, 100, True)
        for i,name in enumerate(self.names):
            draw_text(f"Player {i+1}:", F_MED, BLACK, SCREEN, SCREEN_WIDTH//2-150, 250+i*150, True)
            r=pygame.Rect(SCREEN_WIDTH//2-250, 300+i*150, 500, 50)
            pygame.draw.rect(SCREEN, LIGHT_GRAY, r); pygame.draw.rect(SCREEN, BLACK if self.active_input==i else GRAY, r, 2)
            draw_text(name, F_MED, BLACK, SCREEN, r.x+10, r.y+5)
        self.buttons["start"].draw(SCREEN)

    def draw_playing(self):
        SCREEN.fill(WHITE)
        pygame.draw.line(SCREEN, GRAY, (SCREEN_WIDTH//2,0), (SCREEN_WIDTH//2,SCREEN_HEIGHT), 4)
        self.draw_player(self.players[0], 0)
        self.draw_player(self.players[1], SCREEN_WIDTH//2)
        cur=self.players[self.turn]
        x=SCREEN_WIDTH//4 + (SCREEN_WIDTH//2)*self.turn
        draw_text(f"Rolls left: {cur.rolls}", F_SML, BLACK, SCREEN, x, SCREEN_HEIGHT-30, True)
        for k in ("roll","quit_ingame","restart"): self.buttons[k].draw(SCREEN)
        if self.yatzy_flash!=-1: draw_text("YATZY!", F_BIG, GOLD, SCREEN, SCREEN_WIDTH//2, SCREEN_HEIGHT//2, True)

    def draw_player(self, p, x0):
        is_cur = (p is self.players[self.turn])
        name_x, name_y = x0+SCREEN_WIDTH//4, 50
        if is_cur:
            w,h = F_MED.size(p.name)
            pygame.draw.rect(SCREEN, GOLD, (name_x-w//2-10, name_y-h//2-5, w+20, h+10), border_radius=5)
        draw_text(p.name, F_MED, BLACK, SCREEN, name_x, name_y, True)
        draw_text("Total Score", F_SML, BLACK, SCREEN, name_x, 100, True)
        draw_text(str(p.total()), F_BIG, BLUE, SCREEN, name_x, 150, True)
        if is_cur and self.advice and self.advice_on:
            for i,line in enumerate(textwrap.wrap(self.advice, width=40)):
                draw_text(line, F_TINY, RED, SCREEN, x0+50, 185 + i*(F_TINY.get_height()+2))
        # 점수판
        y0,h = 220,35; y_upper_end=y0+6*h
        for i,cat in enumerate(SCORE_CATS):
            y = y0+i*h if i<6 else y_upper_end+70+(i-6)*h
            if i==6: pygame.draw.line(SCREEN, GRAY, (x0+40, y-18), (x0+SCREEN_WIDTH//2-40, y-18), 2)
            r=pygame.Rect(x0+40, y-10, SCREEN_WIDTH//2-80, h)
            selectable = is_cur and p.scores[cat] is None and p.rolls<3
            hovered = r.collidepoint(self.mouse)
            if selectable and hovered: pygame.draw.rect(SCREEN, LIGHT_GRAY, r, border_radius=5)
            draw_text(cat, F_SML, BLUE if selectable and hovered else BLACK, SCREEN, x0+50, y)
            if p.scores[cat] is not None:
                draw_text(str(p.scores[cat]), F_SML, BLACK, SCREEN, x0+450, y)
            elif selectable:
                is_yat = len(set(p.dice))==1 and p.dice[0]!=0
                is_bonus = is_yat and p.yatzy_hits>=1
                pts = 50 if is_yat else calc_score(cat, p.dice)
                draw_text(str(pts), F_SML, BLUE if hovered else GREEN, SCREEN, x0+450, y)
        draw_text(f"Upper Total: {p.get_upper()} / 63", F_TINY, BLACK, SCREEN, x0+50, y_upper_end+10)
        draw_text(f"Bonus: {p.bonus()}", F_TINY, GOLD if p.bonus()>0 else BLACK, SCREEN, x0+SCREEN_WIDTH//2-120, y_upper_end+35)
        # 주사위
        if any(d>0 for d in p.dice):
            for i,val in enumerate(p.dice):
                r=pygame.Rect(x0+80+i*100, SCREEN_HEIGHT-200, 80,80)
                pygame.draw.rect(SCREEN, BLACK, r, 2, border_radius=10)
                draw_dice_face(SCREEN, val, r)
                if p.held[i]: pygame.draw.rect(SCREEN, RED, r, 4, border_radius=10)

    def draw_game_over(self):
        self.draw_playing(); self._overlay(220)
        s1,s2 = self.players[0].total(), self.players[1].total()
        winner = f"{self.players[0].name} Wins!" if s1>s2 else f"{self.players[1].name} Wins!" if s2>s1 else "It's a Tie!"
        draw_text("GAME OVER", F_BIG, GOLD, SCREEN, SCREEN_WIDTH//2, 200, True)
        draw_text(winner, F_MED, WHITE, SCREEN, SCREEN_WIDTH//2, 300, True)
        draw_text(f"{self.players[0].name}: {s1} vs {self.players[1].name}: {s2}", F_SML, GRAY, SCREEN, SCREEN_WIDTH//2, 360, True)
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