from flask import Flask, request, jsonify
from flask_cors import CORS
import uuid
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)  # 允许跨域请求

# 内存中的玩家数据存储
players = {}
# 玩家活跃状态跟踪（用于清理不活跃玩家）
player_last_activity = {}
# 追踪每个问题的奖励状态 - {question_id: {"bonus_awarded": True, "first_correct_player": player_id, "awarded_at": timestamp}}
question_bonus_status = {}
# 存储每个玩家每个问题的回答时间 - {player_id: {question_id: {"time_spent_ms": int, "answered_at": timestamp, "correct": bool}}}
player_question_times = {}

# 配置
PLAYER_TIMEOUT_MINUTES = 30  # 30分钟后清理不活跃玩家
FIRST_CORRECT_BONUS = 10     # 第一个答对问题的奖励分数

def cleanup_inactive_players():
    """清理超过指定时间未活跃的玩家"""
    current_time = datetime.now()
    inactive_players = []
    
    for player_id, last_activity in player_last_activity.items():
        if current_time - last_activity > timedelta(minutes=PLAYER_TIMEOUT_MINUTES):
            inactive_players.append(player_id)
    
    for player_id in inactive_players:
        if player_id in players:
            del players[player_id]
        if player_id in player_last_activity:
            del player_last_activity[player_id]
        if player_id in player_question_times:
            del player_question_times[player_id]
    
    return len(inactive_players)

@app.route('/register', methods=['POST'])
def register_player():
    """注册新玩家"""
    try:
        data = request.get_json()
        
        if not data or 'name' not in data:
            return jsonify({"detail": "Name is required"}), 400
        
        name = data['name'].strip()
        if not name:
            return jsonify({"detail": "Name cannot be empty"}), 400
        
        # 生成唯一的玩家ID
        player_id = str(uuid.uuid4())
        
        # 创建玩家数据
        player_data = {
            "player_id": player_id,
            "name": name,
            "score": 0,
            "current_question_number": 0,
            "total_questions_in_game": 0,
            "status": "waiting",  # waiting, playing, finished
            "registered_at": datetime.now().isoformat(),
            "bonus_earned": 0  # 追踪玩家获得的奖励分数
        }
        
        # 存储玩家数据
        players[player_id] = player_data
        player_last_activity[player_id] = datetime.now()
        # 初始化玩家回答时间记录
        player_question_times[player_id] = {}
        
        # 清理不活跃的玩家
        cleanup_inactive_players()
        
        return jsonify({
            "message": f"Welcome, {name}! You have been registered successfully.",
            "player_id": player_id,
            "player_data": player_data
        }), 200
        
    except Exception as e:
        return jsonify({"detail": f"Server error: {str(e)}"}), 500

@app.route('/update_status', methods=['POST'])
def update_player_status():
    """更新玩家状态"""
    try:
        data = request.get_json()
        
        if not data or 'player_id' not in data:
            return jsonify({"detail": "Player ID is required"}), 400
        
        player_id = data['player_id']
        
        if player_id not in players:
            return jsonify({"detail": "Player not found"}), 404
        
        # 更新玩家活跃时间
        player_last_activity[player_id] = datetime.now()
        
        # 更新玩家数据
        player = players[player_id]
        
        # 初始化玩家回答时间记录（如果不存在）
        if player_id not in player_question_times:
            player_question_times[player_id] = {}
        
        # 处理问题回答相关的数据
        bonus_awarded = False
        bonus_points = 0
        
        if 'question_id' in data and 'time_spent_ms' in data and 'last_answer_correct' in data:
            question_id = data['question_id']
            time_spent_ms = data['time_spent_ms']
            is_correct = data['last_answer_correct']
            answered_at = datetime.now().isoformat()
            
            # 存储回答时间和正确性
            player_question_times[player_id][question_id] = {
                "time_spent_ms": time_spent_ms,
                "answered_at": answered_at,
                "correct": is_correct
            }
            
            # 检查是否需要给予第一个答对的奖励
            if is_correct:
                if question_id not in question_bonus_status:
                    # 这是第一个答对这个问题的玩家，给予奖励
                    question_bonus_status[question_id] = {
                        "bonus_awarded": True,
                        "first_correct_player": player_id,
                        "awarded_at": answered_at
                    }
                    bonus_awarded = True
                    bonus_points = FIRST_CORRECT_BONUS
                    player['bonus_earned'] = player.get('bonus_earned', 0) + bonus_points
                    
                    # 如果客户端已经发送了score，我们需要在其基础上加上奖励
                    if 'score' in data:
                        player['score'] = data['score'] + bonus_points
                    else:
                        player['score'] = player.get('score', 0) + bonus_points
                else:
                    # 已经有人答对了，不给奖励，但要更新分数
                    if 'score' in data:
                        player['score'] = data['score']
            else:
                # 答错了，直接更新分数（如果提供了）
                if 'score' in data:
                    player['score'] = data['score']
        
        # 更新其他可选字段
        if 'name' in data:
            player['name'] = data['name']
        if 'current_question_number' in data:
            player['current_question_number'] = data['current_question_number']
        if 'total_questions_in_game' in data:
            player['total_questions_in_game'] = data['total_questions_in_game']
        if 'status' in data:
            player['status'] = data['status']
        
        # 如果没有处理问题回答但有score字段，直接更新
        if 'score' in data and 'question_id' not in data:
            player['score'] = data['score']
        
        player['last_updated'] = datetime.now().isoformat()
        
        response_data = {
            "message": "Player status updated successfully",
            "player_data": player
        }
        
        # 如果获得了奖励，在响应中包含奖励信息
        if bonus_awarded:
            response_data["bonus_info"] = {
                "bonus_awarded": True,
                "bonus_points": bonus_points,
                "reason": "First correct answer for this question",
                "question_id": question_id
            }
        
        return jsonify(response_data), 200
        
    except Exception as e:
        return jsonify({"detail": f"Server error: {str(e)}"}), 500

@app.route('/dashboard', methods=['GET'])
def get_dashboard():
    """获取所有玩家的数据用于实时仪表板，包含详细答题记录"""
    try:
        # 清理不活跃的玩家
        cleanup_inactive_players()
        
        # 返回所有活跃玩家的数据，包含详细答题信息
        active_players = []
        
        for player_id, player_data in players.items():
            # 获取该玩家的答题记录
            player_questions = player_question_times.get(player_id, {})
            
            # 为每个问题构建详细状态
            question_details = {}
            for question_id in range(1, 6):  # Q1-Q5 (改为5个问题)
                question_details[str(question_id)] = {
                    "answered": str(question_id) in player_questions,
                    "correct": False,
                    "fastest": False,
                    "time_spent_ms": 0,
                    "answered_at": None
                }
                
                # 如果该问题已回答，填充详细信息
                if str(question_id) in player_questions:
                    answer_data = player_questions[str(question_id)]
                    question_details[str(question_id)].update({
                        "correct": answer_data["correct"],
                        "time_spent_ms": answer_data["time_spent_ms"],
                        "answered_at": answer_data["answered_at"]
                    })
                    
                    # 检查是否是最快答对的
                    if (answer_data["correct"] and 
                        str(question_id) in question_bonus_status and 
                        question_bonus_status[str(question_id)]["first_correct_player"] == player_id):
                        question_details[str(question_id)]["fastest"] = True
            
            # 构建包含详细信息的玩家数据
            enhanced_player_data = player_data.copy()
            enhanced_player_data["question_details"] = question_details
            active_players.append(enhanced_player_data)
        
        # 按分数降序排序，然后按姓名升序排序
        active_players.sort(key=lambda x: (-x['score'], x['name']))
        
        return jsonify(active_players), 200
        
    except Exception as e:
        return jsonify({"detail": f"Server error: {str(e)}"}), 500

@app.route('/player/<player_id>/question_status', methods=['GET'])
def get_player_question_status(player_id):
    """获取特定玩家的所有问题答题状态"""
    try:
        if player_id not in players:
            return jsonify({"detail": "Player not found"}), 404
        
        player_questions = player_question_times.get(player_id, {})
        question_status = {}
        
        for question_id in range(1, 6):  # Q1-Q5 (改为5个问题)
            question_status[str(question_id)] = {
                "answered": str(question_id) in player_questions,
                "correct": False,
                "fastest": False,
                "time_spent_ms": 0,
                "answered_at": None
            }
            
            if str(question_id) in player_questions:
                answer_data = player_questions[str(question_id)]
                question_status[str(question_id)].update({
                    "correct": answer_data["correct"],
                    "time_spent_ms": answer_data["time_spent_ms"],
                    "answered_at": answer_data["answered_at"]
                })
                
                # 检查是否是最快答对的
                if (answer_data["correct"] and 
                    str(question_id) in question_bonus_status and 
                    question_bonus_status[str(question_id)]["first_correct_player"] == player_id):
                    question_status[str(question_id)]["fastest"] = True
        
        return jsonify({
            "player_id": player_id,
            "player_name": players[player_id]["name"],
            "question_status": question_status
        }), 200
        
    except Exception as e:
        return jsonify({"detail": f"Server error: {str(e)}"}), 500

@app.route('/cleanup', methods=['GET', 'POST'])
def cleanup_game_state():
    """清理游戏状态 - 支持GET和POST方法，用于下一轮游戏"""
    try:
        # 清理所有数据
        players.clear()
        player_last_activity.clear()
        question_bonus_status.clear()
        player_question_times.clear()
        
        return jsonify({
            "message": "All game data has been cleared successfully",
            "active_players_count": 0,
            "cleanup_timestamp": datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        return jsonify({"detail": f"Server error: {str(e)}"}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """健康检查端点"""
    try:
        cleanup_inactive_players()
        
        return jsonify({
            "status": "healthy",
            "active_players": len(players),
            "questions_with_bonus": len(question_bonus_status),
            "server_time": datetime.now().isoformat(),
            "uptime_info": "Server is running normally"
        }), 200
        
    except Exception as e:
        return jsonify({"detail": f"Health check failed: {str(e)}"}), 500

@app.route('/stats', methods=['GET'])
def get_game_stats():
    """获取游戏统计信息"""
    try:
        cleanup_inactive_players()
        
        if not players:
            return jsonify({
                "total_players": 0,
                "average_score": 0,
                "highest_score": 0,
                "players_by_status": {},
                "question_stats": {},
                "bonus_stats": {}
            }), 200
        
        scores = [p['score'] for p in players.values()]
        status_counts = {}
        total_bonuses = sum(p.get('bonus_earned', 0) for p in players.values())
        
        for player in players.values():
            status = player['status']
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # 计算问题统计
        question_stats = {}
        for player_id, question_times in player_question_times.items():
            for question_id, time_data in question_times.items():
                if question_id not in question_stats:
                    question_stats[question_id] = {
                        "total_attempts": 0,
                        "correct_attempts": 0,
                        "average_time_ms": 0,
                        "min_time_ms": float('inf'),
                        "max_time_ms": 0
                    }
                
                stats = question_stats[question_id]
                stats["total_attempts"] += 1
                if time_data["correct"]:
                    stats["correct_attempts"] += 1
                
                time_ms = time_data["time_spent_ms"]
                stats["min_time_ms"] = min(stats["min_time_ms"], time_ms)
                stats["max_time_ms"] = max(stats["max_time_ms"], time_ms)
        
        # 计算平均时间
        for question_id, stats in question_stats.items():
            times = [time_data["time_spent_ms"] for player_times in player_question_times.values() 
                    for qid, time_data in player_times.items() if qid == question_id]
            if times:
                stats["average_time_ms"] = sum(times) / len(times)
            if stats["min_time_ms"] == float('inf'):
                stats["min_time_ms"] = 0
        
        stats = {
            "total_players": len(players),
            "average_score": sum(scores) / len(scores) if scores else 0,
            "highest_score": max(scores) if scores else 0,
            "lowest_score": min(scores) if scores else 0,
            "players_by_status": status_counts,
            "question_stats": question_stats,
            "bonus_stats": {
                "total_bonuses_awarded": len(question_bonus_status),
                "total_bonus_points": total_bonuses,
                "questions_with_bonus": list(question_bonus_status.keys())
            },
            "last_updated": datetime.now().isoformat()
        }
        
        return jsonify(stats), 200
        
    except Exception as e:
        return jsonify({"detail": f"Server error: {str(e)}"}), 500

@app.route('/player/<player_id>/times', methods=['GET'])
def get_player_times(player_id):
    """获取特定玩家的回答时间详情"""
    try:
        if player_id not in players:
            return jsonify({"detail": "Player not found"}), 404
        
        if player_id not in player_question_times:
            return jsonify({"player_id": player_id, "question_times": {}}), 200
        
        return jsonify({
            "player_id": player_id,
            "player_name": players[player_id]["name"],
            "question_times": player_question_times[player_id]
        }), 200
        
    except Exception as e:
        return jsonify({"detail": f"Server error: {str(e)}"}), 500

@app.route('/question/<int:question_id>/stats', methods=['GET'])
def get_question_stats(question_id):
    """获取特定问题的统计信息"""
    try:
        # 收集这个问题的所有回答
        question_answers = []
        for player_id, question_times in player_question_times.items():
            if question_id in question_times:
                answer_data = question_times[question_id].copy()
                answer_data["player_id"] = player_id
                answer_data["player_name"] = players.get(player_id, {}).get("name", "Unknown")
                question_answers.append(answer_data)
        
        # 计算统计信息
        if not question_answers:
            return jsonify({
                "question_id": question_id,
                "total_attempts": 0,
                "correct_attempts": 0,
                "accuracy_rate": 0,
                "average_time_ms": 0,
                "bonus_awarded": question_id in question_bonus_status,
                "answers": []
            }), 200
        
        correct_count = sum(1 for answer in question_answers if answer["correct"])
        times = [answer["time_spent_ms"] for answer in question_answers]
        
        result = {
            "question_id": question_id,
            "total_attempts": len(question_answers),
            "correct_attempts": correct_count,
            "accuracy_rate": correct_count / len(question_answers) * 100,
            "average_time_ms": sum(times) / len(times),
            "min_time_ms": min(times),
            "max_time_ms": max(times),
            "bonus_awarded": question_id in question_bonus_status,
            "bonus_info": question_bonus_status.get(question_id, {}),
            "answers": sorted(question_answers, key=lambda x: x["answered_at"])
        }
        
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({"detail": f"Server error: {str(e)}"}), 500

if __name__ == '__main__':
    print("🎮 数据治理挑战游戏服务器启动中...")
    print("📊 仪表板: http://localhost:5000/dashboard")
    print("🏥 健康检查: http://localhost:5000/health")
    print("📈 游戏统计: http://localhost:5000/stats")
    print("🧹 清理数据: http://localhost:5000/cleanup")
    print("⏱️  玩家时间: http://localhost:5000/player/{player_id}/times")
    print("❓ 问题统计: http://localhost:5000/question/{question_id}/stats")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=5000, debug=True) 