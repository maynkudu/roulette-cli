import random


class RouletteEngine:
    def __init__(self):
        self.colors = {0: "green"}
        red_numbers = [
            1,
            3,
            5,
            7,
            9,
            12,
            14,
            16,
            18,
            19,
            21,
            23,
            25,
            27,
            30,
            32,
            34,
            36,
        ]
        for n in range(1, 37):
            self.colors[n] = "red" if n in red_numbers else "black"

    def spin(self):
        res = random.randint(0, 36)
        return res, self.colors[res]

    def calculate_payout(self, bet_type, choice, amount, win_num, win_color):
        if bet_type == "number" and str(choice) == str(win_num):
            return amount * 35
        if bet_type == "color" and str(choice).lower() == win_color:
            return amount * 1
        return -amount
