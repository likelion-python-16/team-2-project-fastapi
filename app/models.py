from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship, DeclarativeBase
from datetime import datetime

# 최신 방식: DeclarativeBase 사용
class Base(DeclarativeBase):
    pass

# User 모델
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, server_default=func.now())  # 최신 방식
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # 관계 설정
    posts = relationship("Post", back_populates="author")
    comments = relationship("Comment", back_populates="author")

# Post 모델
class Post(Base):
    __tablename__ = "posts"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # 관계 설정
    author = relationship("User", back_populates="posts")
    comments = relationship("Comment", back_populates="post")

# Comment 모델
class Comment(Base):
    __tablename__ = "comments"
    
    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # 관계 설정
    post = relationship("Post", back_populates="comments")
    author = relationship("User", back_populates="comments")