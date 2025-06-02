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

# 配置
PLAYER_TIMEOUT_MINUTES = 30  # 30分钟后清理不活跃玩家

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
            "registered_at": datetime.now().isoformat()
        }
        
        # 存储玩家数据
        players[player_id] = player_data
        player_last_activity[player_id] = datetime.now()
        
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
        
        # 更新可选字段
        if 'name' in data:
            player['name'] = data['name']
        if 'score' in data:
            player['score'] = data['score']
        if 'current_question_number' in data:
            player['current_question_number'] = data['current_question_number']
        if 'total_questions_in_game' in data:
            player['total_questions_in_game'] = data['total_questions_in_game']
        if 'status' in data:
            player['status'] = data['status']
        
        player['last_updated'] = datetime.now().isoformat()
        
        return jsonify({
            "message": "Player status updated successfully",
            "player_data": player
        }), 200
        
    except Exception as e:
        return jsonify({"detail": f"Server error: {str(e)}"}), 500

@app.route('/dashboard', methods=['GET'])
def get_dashboard():
    """获取所有玩家的数据用于实时仪表板"""
    try:
        # 清理不活跃的玩家
        cleanup_inactive_players()
        
        # 返回所有活跃玩家的数据
        active_players = list(players.values())
        
        # 按分数降序排序，然后按姓名升序排序
        active_players.sort(key=lambda x: (-x['score'], x['name']))
        
        return jsonify(active_players), 200
        
    except Exception as e:
        return jsonify({"detail": f"Server error: {str(e)}"}), 500

@app.route('/cleanup', methods=['GET', 'POST'])
def cleanup_game_state():
    """清理游戏状态 - 支持GET和POST方法，用于下一轮游戏"""
    try:
        # 清理所有数据
        players.clear()
        player_last_activity.clear()
        
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
                "players_by_status": {}
            }), 200
        
        scores = [p['score'] for p in players.values()]
        status_counts = {}
        
        for player in players.values():
            status = player['status']
            status_counts[status] = status_counts.get(status, 0) + 1
        
        stats = {
            "total_players": len(players),
            "average_score": sum(scores) / len(scores) if scores else 0,
            "highest_score": max(scores) if scores else 0,
            "lowest_score": min(scores) if scores else 0,
            "players_by_status": status_counts,
            "last_updated": datetime.now().isoformat()
        }
        
        return jsonify(stats), 200
        
    except Exception as e:
        return jsonify({"detail": f"Server error: {str(e)}"}), 500

if __name__ == '__main__':
    print("🎮 数据治理挑战游戏服务器启动中...")
    print("📊 仪表板: http://localhost:5000/dashboard")
    print("🏥 健康检查: http://localhost:5000/health")
    print("📈 游戏统计: http://localhost:5000/stats")
    print("🧹 清理数据: http://localhost:5000/cleanup")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=5000, debug=True) 