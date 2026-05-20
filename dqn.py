import tensorflow as tf
from keras.models import Sequential
from keras.layers import Conv2D, Flatten, Dense, Input
from keras.losses import Huber
from keras.optimizers import Adam
import numpy as np
from collections import deque
import random
import pickle
import os
import tkinter as tk
import cshogi

# 常數設定
BOARD_SIZE = 9
GRID_SIZE = 50
PADDING = 40
MODEL_WEIGHTS_PATH = 'shogi_dqn.weights.h5'
REPLAY_MEMORY_PATH = 'shogi_replay_memory.pkl'
ACTION_SIZE = 2187  # 動作空間大小

# 棋子漢字顯示 (使用 piece type)
PIECE_KANJI = {
    cshogi.PAWN: '歩', cshogi.LANCE: '香', cshogi.KNIGHT: '桂',
    cshogi.SILVER: '銀', cshogi.GOLD: '金', cshogi.BISHOP: '角',
    cshogi.ROOK: '飛', cshogi.KING: '王',
    cshogi.PROM_PAWN: 'と', cshogi.PROM_LANCE: '杏', cshogi.PROM_KNIGHT: '圭',
    cshogi.PROM_SILVER: '全', cshogi.PROM_BISHOP: '馬', cshogi.PROM_ROOK: '龍',
}

# 持駒類型
HAND_PIECE_TYPES = [cshogi.HPAWN, cshogi.HLANCE, cshogi.HKNIGHT, cshogi.HSILVER,
                    cshogi.HGOLD, cshogi.HBISHOP, cshogi.HROOK]

HAND_PIECE_KANJI = {
    cshogi.HPAWN: '歩', cshogi.HLANCE: '香', cshogi.HKNIGHT: '桂',
    cshogi.HSILVER: '銀', cshogi.HGOLD: '金', cshogi.HBISHOP: '角', cshogi.HROOK: '飛'
}

# 駒種類列表
PIECE_TYPES = [cshogi.PAWN, cshogi.LANCE, cshogi.KNIGHT, cshogi.SILVER,
               cshogi.GOLD, cshogi.BISHOP, cshogi.ROOK, cshogi.KING,
               cshogi.PROM_PAWN, cshogi.PROM_LANCE, cshogi.PROM_KNIGHT,
               cshogi.PROM_SILVER, cshogi.PROM_BISHOP, cshogi.PROM_ROOK]


class DQN:
    def __init__(self):
        self.epsilon = 1.0
        self.epsilon_min = 0.05
        self.epsilon_decay = 0.9995
        self.gamma = 0.98
        self.memory_size = 5000
        self.memory = deque(maxlen=self.memory_size)
        
        # 先定義 action_size，再建立網路
        self.action_size = ACTION_SIZE
        
        self.model = self.build_net()
        self.target_model = self.build_net()
        self.update_target_net()

    def build_net(self):
        model = Sequential()
        model.add(Input(shape=(9, 9, 30)))
        model.add(Conv2D(64, (3, 3), activation='relu', padding='same'))
        model.add(Conv2D(128, (3, 3), activation='relu', padding='same'))
        model.add(Conv2D(128, (3, 3), activation='relu', padding='same'))
        model.add(Flatten())
        model.add(Dense(256, activation='relu'))
        model.add(Dense(self.action_size))
        model.compile(
            optimizer=Adam(learning_rate=1e-4),
            loss=Huber()
        )
        return model

    def board_to_state(self, board, turn):
        """將 cshogi 棋盤轉換為神經網路輸入狀態"""
        state = np.zeros((9, 9, 30), dtype=np.float32)
        
        for sq in range(81):
            piece = board.piece(sq)
            if piece is not None and piece != 0:
                row = sq // 9
                col = sq % 9
                
                if turn == cshogi.WHITE:
                    row = 8 - row
                    col = 8 - col
                
                piece_type = cshogi.piece_to_piece_type(piece)
                is_black_piece = piece < 16
                
                if (turn == cshogi.BLACK and is_black_piece) or (turn == cshogi.WHITE and not is_black_piece):
                    channel_offset = 0
                else:
                    channel_offset = 14
                
                if piece_type in PIECE_TYPES:
                    channel = channel_offset + PIECE_TYPES.index(piece_type)
                    if channel < 28:
                        state[row, col, channel] = 1.0
        
        my_hand_idx = 0 if turn == cshogi.BLACK else 1
        opp_hand_idx = 1 - my_hand_idx
        
        my_hand_count = 0
        opp_hand_count = 0
        
        for hp in HAND_PIECE_TYPES:
            my_hand_count += board.pieces_in_hand[my_hand_idx][hp]
            opp_hand_count += board.pieces_in_hand[opp_hand_idx][hp]
        
        state[:, :, 28] = my_hand_count / 38.0
        state[:, :, 29] = opp_hand_count / 38.0
        
        return state

    def move_to_action(self, move):
        """將 cshogi move 轉換為動作索引"""
        return move % self.action_size

    def get_qvalue(self, board, turn):
        state = self.board_to_state(board, turn)
        state = np.expand_dims(state, axis=0)
        q_values = self.model.predict(state, verbose=0)
        return q_values[0]

    def epsilon_greedy(self, board):
        legal_moves = list(board.legal_moves)
        if len(legal_moves) == 0:
            return None
            
        if np.random.rand() < self.epsilon:
            return random.choice(legal_moves)
        else:
            q_values = self.get_qvalue(board, board.turn)
            best_move = None
            best_q = float('-inf')
            
            for move in legal_moves:
                action_idx = self.move_to_action(move)
                if q_values[action_idx] > best_q:
                    best_q = q_values[action_idx]
                    best_move = move
            
            return best_move if best_move else random.choice(legal_moves)

    def update_target_net(self):
        self.target_model.set_weights(self.model.get_weights())

    def remember(self, state, action, reward, next_state, done):
        self.memory.append((state, action, reward, next_state, done))

    def train_step(self, batch_size=32):
        if len(self.memory) < batch_size:
            return 0

        minibatch = random.sample(self.memory, batch_size)
        states, actions, rewards, next_states, dones = zip(*minibatch)

        states = np.array(states)
        actions = np.array(actions)
        rewards = np.array(rewards)
        next_states = np.array(next_states)
        dones = np.array(dones)

        q_values = self.model.predict(states, verbose=0)
        next_q_values = self.target_model.predict(next_states, verbose=0)

        targets = q_values.copy()
        for i in range(batch_size):
            if dones[i]:
                targets[i, actions[i]] = rewards[i]
            else:
                targets[i, actions[i]] = rewards[i] + self.gamma * np.max(next_q_values[i])

        loss = self.model.fit(states, targets, epochs=1, verbose=0)
        return loss.history['loss'][0]

    def save_progress(self, game_count):
        print("\n正在保存進度...")
        self.model.save_weights(MODEL_WEIGHTS_PATH)
        data_to_save = {
            'memory': list(self.memory),
            'epsilon': self.epsilon,
            'game_count': game_count
        }
        with open(REPLAY_MEMORY_PATH, 'wb') as f:
            pickle.dump(data_to_save, f)
        print(f"進度已保存！局數: {game_count}")

    def load_progress(self):
        game_count = 0
        print("正在嘗試載入過往進度...")
        if os.path.exists(MODEL_WEIGHTS_PATH):
            self.model.load_weights(MODEL_WEIGHTS_PATH)
            self.update_target_net()
            print(f"成功載入模型權重: {MODEL_WEIGHTS_PATH}")
        else:
            print("未找到模型權重檔案，將使用新模型。")

        if os.path.exists(REPLAY_MEMORY_PATH):
            with open(REPLAY_MEMORY_PATH, 'rb') as f:
                saved_data = pickle.load(f)
                self.memory = deque(saved_data['memory'], maxlen=self.memory_size)
                self.epsilon = saved_data['epsilon']
                game_count = saved_data['game_count']
            print(f"成功載入經驗資料，已恢復到第 {game_count} 局")
        else:
            print("未找到經驗資料檔案，將從零開始收集。")
        
        return game_count


class ShogiApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("將棋 DQN 自我對弈訓練")
        
        canvas_width = GRID_SIZE * BOARD_SIZE + PADDING * 2
        canvas_height = GRID_SIZE * BOARD_SIZE + PADDING * 2 + 100
        
        self.canvas = tk.Canvas(self, width=canvas_width, height=canvas_height, background="#e8c170")
        self.canvas.pack()
        
        self.board = cshogi.Board()
        
        self.agent = DQN()
        self.game_count = self.agent.load_progress()
        
        self.sente_wins = 0
        self.gote_wins = 0
        self.draws = 0
        self.moves_this_game = 0
        self.total_loss = 0
        self.loss_count = 0
        
        print(f"目前使用的 Epsilon (探索率): {self.agent.epsilon:.4f}")
        
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.draw_board()
        self.after(500, self.next_turn)

    def draw_board(self):
        self.canvas.delete("all")
        
        for i in range(BOARD_SIZE + 1):
            y = PADDING + i * GRID_SIZE
            self.canvas.create_line(PADDING, y, PADDING + GRID_SIZE * BOARD_SIZE, y, fill="#8B7355", width=1)
            x = PADDING + i * GRID_SIZE
            self.canvas.create_line(x, PADDING, x, PADDING + GRID_SIZE * BOARD_SIZE, fill="#8B7355", width=1)
        
        for i in range(BOARD_SIZE):
            x = PADDING + i * GRID_SIZE + GRID_SIZE // 2
            self.canvas.create_text(x, PADDING - 15, text=str(9 - i), font=("Arial", 10), fill="#555")
            y = PADDING + i * GRID_SIZE + GRID_SIZE // 2
            row_labels = ['一', '二', '三', '四', '五', '六', '七', '八', '九']
            self.canvas.create_text(PADDING + GRID_SIZE * BOARD_SIZE + 15, y, 
                                   text=row_labels[i], font=("Arial", 10), fill="#555")
        
        for sq in range(81):
            piece = self.board.piece(sq)
            if piece is not None and piece != 0:
                row = sq // 9
                col = sq % 9
                self.draw_piece(row, col, piece)
        
        self.draw_hands()
        self.draw_info()

    def draw_piece(self, row, col, piece):
        x = PADDING + col * GRID_SIZE + GRID_SIZE // 2
        y = PADDING + row * GRID_SIZE + GRID_SIZE // 2
        
        is_sente = piece < 16
        piece_type = cshogi.piece_to_piece_type(piece)
        
        size = GRID_SIZE * 0.4
        fill_color = "#FFF8DC" if is_sente else "#E8E8E8"
        
        if is_sente:
            points = [
                x, y - size,
                x + size * 0.8, y - size * 0.5,
                x + size * 0.8, y + size,
                x - size * 0.8, y + size,
                x - size * 0.8, y - size * 0.5,
            ]
        else:
            points = [
                x, y + size,
                x - size * 0.8, y + size * 0.5,
                x - size * 0.8, y - size,
                x + size * 0.8, y - size,
                x + size * 0.8, y + size * 0.5,
            ]
        
        self.canvas.create_polygon(points, fill=fill_color, outline="#333", width=1)
        
        kanji = PIECE_KANJI.get(piece_type, '?')
        is_promoted = piece_type in [cshogi.PROM_PAWN, cshogi.PROM_LANCE, cshogi.PROM_KNIGHT,
                                     cshogi.PROM_SILVER, cshogi.PROM_BISHOP, cshogi.PROM_ROOK]
        text_color = "#B22222" if is_promoted else "#000"
        
        self.canvas.create_text(x, y, text=kanji, font=("Arial", int(GRID_SIZE * 0.35), "bold"), 
                               fill=text_color)

    def draw_hands(self):
        y_sente = PADDING + GRID_SIZE * BOARD_SIZE + 30
        y_gote = PADDING - 30
        
        self.canvas.create_text(PADDING, y_gote, text="☖後手持駒:", anchor="w", 
                               font=("Arial", 10), fill="#555")
        hand_text_gote = self.get_hand_text(1)
        self.canvas.create_text(PADDING + 80, y_gote, text=hand_text_gote, anchor="w",
                               font=("Arial", 10), fill="#333")
        
        self.canvas.create_text(PADDING, y_sente, text="☗先手持駒:", anchor="w",
                               font=("Arial", 10), fill="#555")
        hand_text_sente = self.get_hand_text(0)
        self.canvas.create_text(PADDING + 80, y_sente, text=hand_text_sente, anchor="w",
                               font=("Arial", 10), fill="#333")

    def get_hand_text(self, color):
        hand = self.board.pieces_in_hand[color]
        parts = []
        
        for hp in HAND_PIECE_TYPES:
            count = hand[hp]
            if count > 0:
                name = HAND_PIECE_KANJI.get(hp, '?')
                if count > 1:
                    parts.append(f"{name}{count}")
                else:
                    parts.append(name)
        
        return ' '.join(parts) if parts else "なし"

    def draw_info(self):
        y_info = PADDING + GRID_SIZE * BOARD_SIZE + 60
        
        turn_text = "先手番" if self.board.turn == cshogi.BLACK else "後手番"
        info_text = f"第{self.game_count + 1}局 | {turn_text} | 第{self.moves_this_game + 1}手 | ε={self.agent.epsilon:.4f}"
        self.canvas.create_text(PADDING, y_info, text=info_text, anchor="w",
                               font=("Arial", 10), fill="#333")
        
        stats_text = f"先手勝: {self.sente_wins} | 後手勝: {self.gote_wins} | 引分: {self.draws}"
        self.canvas.create_text(PADDING, y_info + 20, text=stats_text, anchor="w",
                               font=("Arial", 10), fill="#555")

    def on_closing(self):
        self.agent.save_progress(self.game_count)
        self.destroy()

    def evaluate_position(self, board, turn):
        piece_values = {
            cshogi.PAWN: 1, cshogi.LANCE: 3, cshogi.KNIGHT: 4,
            cshogi.SILVER: 5, cshogi.GOLD: 6, cshogi.BISHOP: 9, cshogi.ROOK: 10,
            cshogi.PROM_PAWN: 7, cshogi.PROM_LANCE: 6, cshogi.PROM_KNIGHT: 6,
            cshogi.PROM_SILVER: 6, cshogi.PROM_BISHOP: 12, cshogi.PROM_ROOK: 13,
            cshogi.KING: 0
        }
        
        hand_piece_to_type = {
            cshogi.HPAWN: cshogi.PAWN, cshogi.HLANCE: cshogi.LANCE,
            cshogi.HKNIGHT: cshogi.KNIGHT, cshogi.HSILVER: cshogi.SILVER,
            cshogi.HGOLD: cshogi.GOLD, cshogi.HBISHOP: cshogi.BISHOP,
            cshogi.HROOK: cshogi.ROOK
        }
        
        score = 0
        
        for sq in range(81):
            piece = board.piece(sq)
            if piece is not None and piece != 0:
                piece_type = cshogi.piece_to_piece_type(piece)
                value = piece_values.get(piece_type, 0)
                is_black_piece = piece < 16
                is_mine = (turn == cshogi.BLACK and is_black_piece) or (turn == cshogi.WHITE and not is_black_piece)
                if is_mine:
                    score += value
                else:
                    score -= value
        
        my_hand_idx = 0 if turn == cshogi.BLACK else 1
        opp_hand_idx = 1 - my_hand_idx
        
        for hp in HAND_PIECE_TYPES:
            pt = hand_piece_to_type.get(hp)
            if pt:
                value = piece_values.get(pt, 0)
                score += value * board.pieces_in_hand[my_hand_idx][hp]
                score -= value * board.pieces_in_hand[opp_hand_idx][hp]
        
        return score * 0.1

    def next_turn(self):
        if self.board.is_game_over():
            self.end_game()
            return
        
        if self.moves_this_game >= 512:
            self.end_game(is_draw=True)
            return
        
        current_turn = self.board.turn
        state_before = self.agent.board_to_state(self.board, current_turn)
        
        move = self.agent.epsilon_greedy(self.board)
        
        if move is None:
            self.end_game()
            return
        
        action_idx = self.agent.move_to_action(move)
        
        self.board.push(move)
        self.moves_this_game += 1
        
        self.draw_board()
        self.update()
        
        if self.board.is_game_over():
            if self.board.is_check():
                reward = -100.0
            else:
                reward = 0
            
            state_after = self.agent.board_to_state(self.board, current_turn)
            self.agent.remember(state_before, action_idx, reward, state_after, True)
            
            if len(self.agent.memory) > 1:
                last_exp = self.agent.memory[-2]
                if last_exp:
                    l_state, l_action, l_reward, l_next, l_done = last_exp
                    opp_reward = -reward if reward != 0 else 0
                    self.agent.memory[-2] = (l_state, l_action, opp_reward, l_next, True)
            
            self.agent.train_step(32)
            self.end_game()
            return
        
        reward = self.evaluate_position(self.board, current_turn)
        state_after = self.agent.board_to_state(self.board, current_turn)
        self.agent.remember(state_before, action_idx, reward, state_after, False)
        
        if self.moves_this_game % 4 == 0:
            loss = self.agent.train_step(32)
            if loss > 0:
                self.total_loss += loss
                self.loss_count += 1
        
        self.after(50, self.next_turn)

    def end_game(self, is_draw=False):
        self.game_count += 1
        
        if is_draw:
            self.draws += 1
            winner_msg = "引き分け"
        elif self.board.is_check():
            if self.board.turn == cshogi.BLACK:
                self.gote_wins += 1
                winner_msg = "後手 (☖) 勝利"
            else:
                self.sente_wins += 1
                winner_msg = "先手 (☗) 勝利"
        else:
            self.draws += 1
            winner_msg = "引き分け"
        
        avg_loss = self.total_loss / max(1, self.loss_count)
        print(f"第{self.game_count}局結束: {winner_msg} | 手數: {self.moves_this_game} | 平均損失: {avg_loss:.6f}")
        
        self.agent.update_target_net()
        
        if self.agent.epsilon > self.agent.epsilon_min:
            self.agent.epsilon *= self.agent.epsilon_decay
        
        if self.game_count % 10 == 0:
            self.agent.save_progress(self.game_count)
        
        self.total_loss = 0
        self.loss_count = 0
        
        self.after(1000, self.reset_game)

    def reset_game(self):
        self.board = cshogi.Board()
        self.moves_this_game = 0
        self.draw_board()
        self.after(500, self.next_turn)


if __name__ == "__main__":
    print("=" * 50)
    print("將棋 DQN 自我對弈訓練系統")
    print("=" * 50)
    print("需要安裝: pip install tensorflow cshogi")
    print("=" * 50)
    
    app = ShogiApp()
    app.mainloop()