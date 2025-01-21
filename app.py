import os
from flask import Flask, request
from flask_socketio import SocketIO, emit, join_room

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*")

connected_clients = {}

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', 'https://nextjs-video-call-and-chat.vercel.app')
    return response

@socketio.on('connect')
def handle_connect():
    print("connect")

@socketio.on('basicInfoOFClientOnConnect')
def handle_client_connect(data):
    room_id = data['roomID']
    user_object = {
        'roomID': room_id,
        'name': data['name'],
        'sid': request.sid
    }

    if room_id not in connected_clients:
        connected_clients[room_id] = []
        connected_clients[room_id].append(user_object)
        join_room(room_id)
        return {
            'isFirstInTheCall': True,
            'name': data['name'],
            'roomFull': False
        }
    
    if any(client['name'] == data['name'] for client in connected_clients[room_id]):
        return {
            'sameName': True,
            'existingName': data['name']
        }

    if len(connected_clients[room_id]) > 0 and len(connected_clients[room_id]) < 4:
        connected_clients[room_id].append(user_object)
        join_room(room_id)
        
        existing_users = [u['name'] for u in connected_clients[room_id] 
                         if u['sid'] != request.sid]
        
        return {
            'isFirstInTheCall': False,
            'membersOnCall': len(connected_clients[room_id]),
            'roomFull': False,
            'existingUsers': existing_users
        }
    
    return {
        'isFirstInTheCall': False,
        'membersOnCall': len(connected_clients[room_id]),
        'roomFull': True
    }

@socketio.on('sendOffer')
def handle_offer(data):
    room_id = data['roomID']
    sender_name = data['senderName']
    target_name = data['targetName']
    offer = data['offer']

    clients_in_room = connected_clients.get(room_id, [])
    target_client = next((client for client in clients_in_room 
                         if client['name'] == target_name), None)

    if target_client:
        emit('receiveOffer', {
            'offer': offer,
            'senderName': sender_name,
            'remoteUsersName': target_name
        }, room=target_client['sid'])

@socketio.on('sendAnswer')
def handle_answer(data):
    room_id = data['roomID']
    sender_name = data['senderName']
    receiver_name = data['receiverName']
    answer = data['answer']

    target_client = next((client for client in connected_clients.get(room_id, [])
                         if client['name'] == receiver_name), None)
    
    if target_client:
        emit('receiveAnswer', {
            'answer': answer,
            'senderName': sender_name
        }, room=target_client['sid'])

@socketio.on('sendIceCandidateToSignalingServer')
def handle_ice_candidate(data):
    emit('receiveIceCandidate', {
        'candidate': data['iceCandidate'],
        'senderName': data['senderName']
    }, room=data['roomID'])

@socketio.on('newMessageFromSender')
def handle_message(data):
    print("newMSG_Object", data['newMSG_Object'])
    emit('newMessageFromReciever', data['newMSG_Object'], room=data['roomID'], include_self=False)

@socketio.on('mediaStateChange')
def handle_media_state(data):
    emit('mediaStateChanged', {
        'userName': data['userName'],
        'enabled': data['enabled'],
        'mediaType': data['mediaType']
    }, room=data['roomID'])

@socketio.on('disconnect')
def handle_disconnect():
    print("Client disconnected:", connected_clients)
    
    for room_id, clients in list(connected_clients.items()):
        disconnected_user_index = next((i for i, client in enumerate(clients)
                                      if client['sid'] == request.sid), -1)

        if disconnected_user_index != -1:
            disconnected_user = clients[disconnected_user_index]
            clients.pop(disconnected_user_index)
            
            if not clients:
                del connected_clients[room_id]
            else:
                emit('userDisconnected', {
                    'name': disconnected_user['name'],
                    'remainingUsers': len(clients)
                }, room=room_id)
            break

if __name__ == '__main__':
    socketio.run(app, 
                 host='0.0.0.0',
                 port=5001,
                 certfile=os.getenv('SSL_CERT_PATH'),
                 keyfile=os.getenv('SSL_KEY_PATH'))