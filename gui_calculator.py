
import tkinter as tk
import math

# 계산기 로직 및 GUI 설정
class Calculator:
    def __init__(self, master):
        self.master = master
        master.title("공학용 계산기")
        self.is_result_displayed = False

        # 결과 표시 화면
        self.display_var = tk.StringVar()
        self.display = tk.Entry(master, textvariable=self.display_var, font=('Arial', 24), bd=10, insertwidth=1, width=16, justify='right')
        self.display.grid(row=0, column=0, columnspan=4)

        # 버튼 레이아웃 정의 (6x4 그리드)
        buttons = [
            'sin', 'cos', 'tan', 'π',
            '(', ')', 'C', '<-',
            '7', '8', '9', '/',
            '4', '5', '6', '*',
            '1', '2', '3', '-',
            '0', '.', '=', '+'
        ]

        # 버튼 생성 및 배치
        row_val = 1
        col_val = 0
        for button_text in buttons:
            action = lambda x=button_text: self.click_event(x)
            tk.Button(master, text=button_text, font=('Arial', 16), width=5, height=2, command=action).grid(row=row_val, column=col_val, sticky="nsew")
            col_val += 1
            if col_val > 3:
                col_val = 0
                row_val += 1

    def click_event(self, key):
        current_text = self.display_var.get()

        # 새 계산 시작 로직
        is_new_input = key.isdigit() or key in ['.', 'sin', 'cos', 'tan', 'π', '(']
        if self.is_result_displayed and is_new_input:
            current_text = ""
            self.is_result_displayed = False
        elif self.is_result_displayed and key in ['+', '-', '*', '/']:
            self.is_result_displayed = False

        if key == 'C':
            self.display_var.set("")
            self.is_result_displayed = False
        elif key == '<-':
            self.display_var.set(current_text[:-1])
            self.is_result_displayed = False
        elif key == '=':
            if not current_text:
                return
            try:
                eval_context = {"sin": math.sin, "cos": math.cos, "tan": math.tan, "pi": math.pi}
                result = eval(current_text, {}, eval_context)

                if isinstance(result, float) and (not math.isfinite(result) or abs(result) > 1e15):
                    raise ValueError()
                
                if isinstance(result, float) and result.is_integer():
                    self.display_var.set(str(int(result)))
                else:
                    self.display_var.set(f"{result:.10f}".rstrip('0').rstrip('.'))
                self.is_result_displayed = True
            except Exception:
                self.display_var.set("정의되지 않음")
                self.is_result_displayed = True
        elif key in ['sin', 'cos', 'tan']:
            self.display_var.set(current_text + key + "(")
        elif key == 'π':
            self.display_var.set(current_text + 'pi')
        else:
            self.display_var.set(current_text + key)

# 메인 프로그램 실행
if __name__ == "__main__":
    root = tk.Tk()
    my_calculator = Calculator(root)
    root.mainloop()
