-- 데이터베이스 초기화 스크립트
-- 이 파일은 MySQL 컨테이너가 처음 시작될 때 실행됩니다

-- 사용자 테이블 생성
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- 게시글 테이블 생성
CREATE TABLE IF NOT EXISTS posts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    content TEXT NOT NULL,
    user_id INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 댓글 테이블 생성
CREATE TABLE IF NOT EXISTS comments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    content TEXT NOT NULL,
    post_id INT,
    user_id INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 테스트 데이터 삽입
INSERT IGNORE INTO users (username, email, password_hash) VALUES
('admin', 'admin@example.com', '$2b$10$example.hash.for.testing'),
('testuser', 'test@example.com', '$2b$10$example.hash.for.testing');

INSERT IGNORE INTO posts (title, content, user_id) VALUES
('첫 번째 게시글', '안녕하세요! 첫 번째 게시글입니다.', 1),
('두 번째 게시글', '두 번째 게시글 내용입니다.', 2);

INSERT IGNORE INTO comments (content, post_id, user_id) VALUES
('좋은 글이네요!', 1, 2),
('감사합니다!', 1, 1);