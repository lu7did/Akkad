import weights

class AlphaZeroTinyNet:
    def __init__(self, hidden_size=16):
        self.hidden_size = hidden_size
        self.w_in = weights.W_IN
        self.w_value = weights.W_VALUE
        self.w_from = weights.W_FROM
        self.w_to = weights.W_TO

