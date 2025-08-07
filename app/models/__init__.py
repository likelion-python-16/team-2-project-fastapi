# Base 클래스를 먼저 import
from .base import Base

# 모든 모델들을 import
from .user import User, Post, Comment

# 나중에 추가될 모델들을 위한 공간
# from .challenge import Challenge, ChallengeParticipant
# from .tag import Tag, UserTag, ChallengeTag
# from .qr import QRCode
# from .chat import ChatRoom, ChatMessage, ChatParticipant

# __all__로 외부에서 import 가능한 것들 정의
__all__ = [
    "Base",
    "User", 
    "Post", 
    "Comment",
    # "Challenge",
    # "ChallengeParticipant",
    # "Tag",
    # "UserTag", 
    # "ChallengeTag",
    # "QRCode",
    # "ChatRoom",
    # "ChatMessage", 
    # "ChatParticipant",
]