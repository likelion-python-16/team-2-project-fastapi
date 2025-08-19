-- MySQL dump 10.13  Distrib 9.4.0, for macos15.4 (arm64)
--
-- Host: 127.0.0.1    Database: team_project_db
-- ------------------------------------------------------
-- Server version	8.0.43

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Current Database: `team_project_db`
--

CREATE DATABASE /*!32312 IF NOT EXISTS*/ `team_project_db` /*!40100 DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci */ /*!80016 DEFAULT ENCRYPTION='N' */;

USE `team_project_db`;

--
-- Table structure for table `admin_notices`
--

DROP TABLE IF EXISTS `admin_notices`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `admin_notices` (
  `id` int NOT NULL AUTO_INCREMENT,
  `author_id` int DEFAULT NULL COMMENT '작성한 관리자 ID',
  `title` varchar(100) NOT NULL,
  `content` text NOT NULL,
  `is_active` tinyint(1) NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_admin_notice_active` (`is_active`),
  KEY `ix_admin_notice_updated` (`updated_at`),
  KEY `ix_admin_notices_id` (`id`),
  KEY `ix_admin_notice_author` (`author_id`),
  CONSTRAINT `admin_notices_ibfk_1` FOREIGN KEY (`author_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `admin_notices`
--

LOCK TABLES `admin_notices` WRITE;
/*!40000 ALTER TABLE `admin_notices` DISABLE KEYS */;
/*!40000 ALTER TABLE `admin_notices` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `alembic_version`
--

DROP TABLE IF EXISTS `alembic_version`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `alembic_version` (
  `version_num` varchar(32) NOT NULL,
  PRIMARY KEY (`version_num`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `alembic_version`
--

LOCK TABLES `alembic_version` WRITE;
/*!40000 ALTER TABLE `alembic_version` DISABLE KEYS */;
/*!40000 ALTER TABLE `alembic_version` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `appeals`
--

DROP TABLE IF EXISTS `appeals`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `appeals` (
  `id` int NOT NULL AUTO_INCREMENT,
  `round_attendance_id` int NOT NULL,
  `explanation` text,
  `files_url` json DEFAULT NULL,
  `submitted_at` datetime NOT NULL,
  `verified_by` int DEFAULT NULL,
  `verified_at` datetime DEFAULT NULL,
  `appeal_status` varchar(20) NOT NULL,
  `note` text,
  `decision_reason` text,
  `decision_code` enum('insufficient_evidence','still_no_gps','time_mismatch','face_mismatch','duplicate','other') DEFAULT NULL,
  `auto_reason` text,
  `is_active` tinyint(1) NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `verified_by` (`verified_by`),
  KEY `ix_appeals_id` (`id`),
  KEY `ix_appeal_status` (`appeal_status`),
  KEY `ix_appeal_ra` (`round_attendance_id`),
  KEY `ix_appeal_submitted` (`submitted_at`),
  CONSTRAINT `appeals_ibfk_1` FOREIGN KEY (`round_attendance_id`) REFERENCES `round_attendances` (`id`) ON DELETE CASCADE,
  CONSTRAINT `appeals_ibfk_2` FOREIGN KEY (`verified_by`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `appeals`
--

LOCK TABLES `appeals` WRITE;
/*!40000 ALTER TABLE `appeals` DISABLE KEYS */;
/*!40000 ALTER TABLE `appeals` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `challenge_embeddings`
--

DROP TABLE IF EXISTS `challenge_embeddings`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `challenge_embeddings` (
  `id` int NOT NULL AUTO_INCREMENT,
  `challenge_id` int NOT NULL,
  `embedding` json NOT NULL,
  `model_name` varchar(100) NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_challenge_embedding_per_model` (`challenge_id`,`model_name`),
  KEY `ix_embedding_challenge` (`challenge_id`),
  KEY `ix_embedding_updated` (`updated_at`),
  KEY `ix_challenge_embeddings_id` (`id`),
  KEY `ix_embedding_model` (`model_name`),
  CONSTRAINT `challenge_embeddings_ibfk_1` FOREIGN KEY (`challenge_id`) REFERENCES `challenges` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `challenge_embeddings`
--

LOCK TABLES `challenge_embeddings` WRITE;
/*!40000 ALTER TABLE `challenge_embeddings` DISABLE KEYS */;
/*!40000 ALTER TABLE `challenge_embeddings` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `challenge_rounds`
--

DROP TABLE IF EXISTS `challenge_rounds`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `challenge_rounds` (
  `id` int NOT NULL AUTO_INCREMENT,
  `challenge_id` int NOT NULL,
  `mode` enum('online','offline') NOT NULL,
  `round` int NOT NULL COMMENT '회차 번호(1,2,3,...)',
  `processing_at` date DEFAULT NULL COMMENT '라운드 진행 날짜(YYYY-MM-DD)',
  `start_time` time DEFAULT NULL COMMENT '시작 시간',
  `finish_time` time DEFAULT NULL COMMENT '종료 시간',
  `description` text COMMENT '회차 설명',
  `url` text COMMENT '안내/참고 URL',
  `created_at` datetime DEFAULT NULL,
  `updated_at` datetime DEFAULT NULL,
  `lat` float DEFAULT NULL COMMENT '위도',
  `lon` float DEFAULT NULL COMMENT '경도',
  `geofence_radius_m` float DEFAULT NULL COMMENT '지오펜스 반경 (미터)',
  `zoom_meeting_id` varchar(255) DEFAULT NULL COMMENT '줌 미팅 ID',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_challenge_roundnum` (`challenge_id`,`round`),
  KEY `ix_round_processing` (`processing_at`),
  KEY `ix_challenge_rounds_id` (`id`),
  KEY `ix_round_mode` (`mode`),
  KEY `ix_round_challenge_round` (`challenge_id`,`round`),
  CONSTRAINT `challenge_rounds_ibfk_1` FOREIGN KEY (`challenge_id`) REFERENCES `challenges` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `challenge_rounds`
--

LOCK TABLES `challenge_rounds` WRITE;
/*!40000 ALTER TABLE `challenge_rounds` DISABLE KEYS */;
/*!40000 ALTER TABLE `challenge_rounds` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `challenge_tags`
--

DROP TABLE IF EXISTS `challenge_tags`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `challenge_tags` (
  `id` int NOT NULL AUTO_INCREMENT,
  `tag_id` int NOT NULL,
  `challenge_id` int NOT NULL,
  `selected_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_challenge_tag_pair` (`tag_id`,`challenge_id`),
  KEY `ix_challenge_tags_id` (`id`),
  KEY `ix_ch_tag_challenge` (`challenge_id`),
  KEY `ix_ch_tag_tag` (`tag_id`),
  CONSTRAINT `challenge_tags_ibfk_1` FOREIGN KEY (`tag_id`) REFERENCES `tags` (`id`) ON DELETE CASCADE,
  CONSTRAINT `challenge_tags_ibfk_2` FOREIGN KEY (`challenge_id`) REFERENCES `challenges` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `challenge_tags`
--

LOCK TABLES `challenge_tags` WRITE;
/*!40000 ALTER TABLE `challenge_tags` DISABLE KEYS */;
/*!40000 ALTER TABLE `challenge_tags` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `challenges`
--

DROP TABLE IF EXISTS `challenges`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `challenges` (
  `id` int NOT NULL AUTO_INCREMENT,
  `title` varchar(100) NOT NULL,
  `description` text,
  `creator_id` int NOT NULL,
  `start_date` date DEFAULT NULL,
  `end_date` date DEFAULT NULL,
  `status` varchar(20) DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `fee` int DEFAULT NULL COMMENT '회비 (원)',
  `participation_fee` int DEFAULT NULL COMMENT '참가비 (원)',
  `min_participants` int DEFAULT NULL COMMENT '최소 참가자 수',
  `max_participants` int DEFAULT NULL COMMENT '최대 참가자 수',
  `use_reward` tinyint(1) DEFAULT NULL COMMENT '리워드 사용 여부',
  `reward` text COMMENT '리워드 내용',
  `total_rounds` int DEFAULT NULL COMMENT '총 회차 수',
  `min_participation_rate` int DEFAULT NULL COMMENT '최소 참여율 (%)',
  `is_closed` tinyint(1) DEFAULT NULL COMMENT '정산 완료 여부',
  `is_deleted` tinyint(1) DEFAULT NULL COMMENT '삭제 여부',
  `deleted_at` datetime DEFAULT NULL COMMENT '삭제 시간',
  `deleted_by` int DEFAULT NULL COMMENT '삭제한 유저',
  PRIMARY KEY (`id`),
  KEY `creator_id` (`creator_id`),
  KEY `deleted_by` (`deleted_by`),
  KEY `ix_challenges_id` (`id`),
  CONSTRAINT `challenges_ibfk_1` FOREIGN KEY (`creator_id`) REFERENCES `users` (`id`),
  CONSTRAINT `challenges_ibfk_2` FOREIGN KEY (`deleted_by`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `challenges`
--

LOCK TABLES `challenges` WRITE;
/*!40000 ALTER TABLE `challenges` DISABLE KEYS */;
/*!40000 ALTER TABLE `challenges` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `chat_messages`
--

DROP TABLE IF EXISTS `chat_messages`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `chat_messages` (
  `id` int NOT NULL AUTO_INCREMENT,
  `room_id` int NOT NULL,
  `sender_id` int NOT NULL,
  `content` text NOT NULL,
  `file_url` varchar(255) DEFAULT NULL,
  `is_read` tinyint(1) NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_chatmsg_room_created` (`room_id`,`created_at`),
  KEY `ix_chatmsg_sender` (`sender_id`),
  KEY `ix_chat_messages_id` (`id`),
  KEY `ix_chatmsg_is_read` (`is_read`),
  CONSTRAINT `chat_messages_ibfk_1` FOREIGN KEY (`room_id`) REFERENCES `chat_rooms` (`id`) ON DELETE CASCADE,
  CONSTRAINT `chat_messages_ibfk_2` FOREIGN KEY (`sender_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `chat_messages`
--

LOCK TABLES `chat_messages` WRITE;
/*!40000 ALTER TABLE `chat_messages` DISABLE KEYS */;
/*!40000 ALTER TABLE `chat_messages` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `chat_participants`
--

DROP TABLE IF EXISTS `chat_participants`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `chat_participants` (
  `id` int NOT NULL AUTO_INCREMENT,
  `room_id` int NOT NULL,
  `user_id` int NOT NULL,
  `joined_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_chat_participant` (`room_id`,`user_id`),
  KEY `ix_chatpart_user` (`user_id`),
  KEY `ix_chat_participants_id` (`id`),
  KEY `ix_chatpart_joined` (`joined_at`),
  KEY `ix_chatpart_room` (`room_id`),
  CONSTRAINT `chat_participants_ibfk_1` FOREIGN KEY (`room_id`) REFERENCES `chat_rooms` (`id`) ON DELETE CASCADE,
  CONSTRAINT `chat_participants_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `chat_participants`
--

LOCK TABLES `chat_participants` WRITE;
/*!40000 ALTER TABLE `chat_participants` DISABLE KEYS */;
/*!40000 ALTER TABLE `chat_participants` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `chat_rooms`
--

DROP TABLE IF EXISTS `chat_rooms`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `chat_rooms` (
  `id` int NOT NULL AUTO_INCREMENT,
  `challenge_id` int NOT NULL,
  `creator_id` int NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_chat_rooms_id` (`id`),
  KEY `ix_chatroom_creator` (`creator_id`),
  KEY `ix_chatroom_created` (`created_at`),
  KEY `ix_chatroom_challenge` (`challenge_id`),
  CONSTRAINT `chat_rooms_ibfk_1` FOREIGN KEY (`challenge_id`) REFERENCES `challenges` (`id`) ON DELETE CASCADE,
  CONSTRAINT `chat_rooms_ibfk_2` FOREIGN KEY (`creator_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `chat_rooms`
--

LOCK TABLES `chat_rooms` WRITE;
/*!40000 ALTER TABLE `chat_rooms` DISABLE KEYS */;
/*!40000 ALTER TABLE `chat_rooms` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `comments`
--

DROP TABLE IF EXISTS `comments`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `comments` (
  `id` int NOT NULL AUTO_INCREMENT,
  `content` text NOT NULL,
  `post_id` int DEFAULT NULL,
  `user_id` int DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `post_id` (`post_id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `comments_ibfk_1` FOREIGN KEY (`post_id`) REFERENCES `posts` (`id`) ON DELETE CASCADE,
  CONSTRAINT `comments_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `comments`
--

LOCK TABLES `comments` WRITE;
/*!40000 ALTER TABLE `comments` DISABLE KEYS */;
INSERT INTO `comments` VALUES (1,'ì¢‹ì€ ê¸€ì´ë„¤ìš”!',1,2,'2025-08-13 06:32:20'),(2,'ê°ì‚¬í•©ë‹ˆë‹¤!',1,1,'2025-08-13 06:32:20');
/*!40000 ALTER TABLE `comments` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `followings`
--

DROP TABLE IF EXISTS `followings`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `followings` (
  `id` int NOT NULL AUTO_INCREMENT,
  `follower_id` int NOT NULL,
  `following_id` int NOT NULL,
  `created_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_follow_pair` (`follower_id`,`following_id`),
  KEY `ix_follow_following` (`following_id`),
  KEY `ix_follow_follower` (`follower_id`),
  KEY `ix_followings_id` (`id`),
  KEY `ix_follow_created` (`created_at`),
  CONSTRAINT `followings_ibfk_1` FOREIGN KEY (`follower_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `followings_ibfk_2` FOREIGN KEY (`following_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `followings`
--

LOCK TABLES `followings` WRITE;
/*!40000 ALTER TABLE `followings` DISABLE KEYS */;
/*!40000 ALTER TABLE `followings` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `invitations`
--

DROP TABLE IF EXISTS `invitations`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `invitations` (
  `id` int NOT NULL AUTO_INCREMENT,
  `challenge_id` int NOT NULL,
  `inviter_id` int NOT NULL,
  `invitee_id` int NOT NULL,
  `reason` text,
  `status` enum('pending','accepted','declined','canceled') NOT NULL,
  `reviewed_by` int DEFAULT NULL,
  `reviewed_at` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_invitation_challenge_invitee` (`challenge_id`,`invitee_id`),
  KEY `reviewed_by` (`reviewed_by`),
  KEY `ix_invitation_invitee` (`invitee_id`),
  KEY `ix_invitations_id` (`id`),
  KEY `ix_invitation_challenge` (`challenge_id`),
  KEY `ix_invitation_status` (`status`),
  KEY `ix_invitation_inviter` (`inviter_id`),
  KEY `ix_invitation_reviewed` (`reviewed_at`),
  CONSTRAINT `invitations_ibfk_1` FOREIGN KEY (`challenge_id`) REFERENCES `challenges` (`id`) ON DELETE CASCADE,
  CONSTRAINT `invitations_ibfk_2` FOREIGN KEY (`inviter_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `invitations_ibfk_3` FOREIGN KEY (`invitee_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `invitations_ibfk_4` FOREIGN KEY (`reviewed_by`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `invitations`
--

LOCK TABLES `invitations` WRITE;
/*!40000 ALTER TABLE `invitations` DISABLE KEYS */;
/*!40000 ALTER TABLE `invitations` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `notifications`
--

DROP TABLE IF EXISTS `notifications`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `notifications` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `title` varchar(100) NOT NULL,
  `content` text,
  `target_type` varchar(30) DEFAULT NULL,
  `target_id` int DEFAULT NULL,
  `is_read` tinyint(1) NOT NULL,
  `event_type` enum('challenge_deleted','creator_delegated','review_created','review_updated','refund_succeeded','refund_failed','point_awarded','notice_posted','join_completed') DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_notification_user` (`user_id`),
  KEY `ix_notification_is_read` (`is_read`),
  KEY `ix_notification_event` (`event_type`),
  KEY `ix_notification_created` (`created_at`),
  KEY `ix_notification_target` (`target_type`,`target_id`),
  KEY `ix_notification_user_read` (`user_id`,`is_read`),
  KEY `ix_notifications_id` (`id`),
  CONSTRAINT `notifications_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `notifications`
--

LOCK TABLES `notifications` WRITE;
/*!40000 ALTER TABLE `notifications` DISABLE KEYS */;
/*!40000 ALTER TABLE `notifications` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `participations`
--

DROP TABLE IF EXISTS `participations`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `participations` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `challenge_id` int NOT NULL,
  `joined_at` datetime NOT NULL,
  `status` varchar(20) NOT NULL,
  `is_active` tinyint(1) NOT NULL,
  `role` enum('creator','participant') NOT NULL,
  `leave_type` varchar(20) DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_participation_user_challenge` (`user_id`,`challenge_id`),
  KEY `ix_participation_status` (`status`),
  KEY `ix_participation_role` (`role`),
  KEY `ix_participations_id` (`id`),
  KEY `ix_participation_joined` (`joined_at`),
  KEY `ix_participation_user` (`user_id`),
  KEY `ix_participation_active` (`is_active`),
  KEY `ix_participation_challenge` (`challenge_id`),
  CONSTRAINT `participations_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `participations_ibfk_2` FOREIGN KEY (`challenge_id`) REFERENCES `challenges` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `participations`
--

LOCK TABLES `participations` WRITE;
/*!40000 ALTER TABLE `participations` DISABLE KEYS */;
/*!40000 ALTER TABLE `participations` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `payments`
--

DROP TABLE IF EXISTS `payments`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `payments` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `challenge_id` int NOT NULL,
  `amount` decimal(12,2) NOT NULL,
  `currency` varchar(3) NOT NULL,
  `payment_type` varchar(20) NOT NULL,
  `status` enum('pending','paid','cancelled','refunded') NOT NULL,
  `toss_payment_id` varchar(100) NOT NULL,
  `idempotency_key` varchar(64) DEFAULT NULL,
  `planner_id_at_payment` int DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_payment_toss` (`toss_payment_id`),
  UNIQUE KEY `uq_payment_idem` (`idempotency_key`),
  KEY `ix_payment_amount` (`amount`),
  KEY `ix_payments_id` (`id`),
  KEY `ix_payment_user_created` (`user_id`,`created_at`),
  KEY `ix_payment_status` (`status`),
  KEY `ix_payment_challenge` (`challenge_id`),
  CONSTRAINT `payments_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT,
  CONSTRAINT `payments_ibfk_2` FOREIGN KEY (`challenge_id`) REFERENCES `challenges` (`id`) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `payments`
--

LOCK TABLES `payments` WRITE;
/*!40000 ALTER TABLE `payments` DISABLE KEYS */;
/*!40000 ALTER TABLE `payments` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `penalty_histories`
--

DROP TABLE IF EXISTS `penalty_histories`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `penalty_histories` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `challenge_id` int DEFAULT NULL,
  `source_type` enum('bad_language','report','frequent_kick','frequent_leave') NOT NULL,
  `reason` varchar(255) NOT NULL,
  `score` int NOT NULL,
  `given_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_penalty_user` (`user_id`),
  KEY `ix_penalty_histories_id` (`id`),
  KEY `ix_penalty_challenge` (`challenge_id`),
  KEY `ix_penalty_given_at` (`given_at`),
  KEY `ix_penalty_source` (`source_type`),
  KEY `ix_penalty_score` (`score`),
  CONSTRAINT `penalty_histories_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `penalty_histories_ibfk_2` FOREIGN KEY (`challenge_id`) REFERENCES `challenges` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `penalty_histories`
--

LOCK TABLES `penalty_histories` WRITE;
/*!40000 ALTER TABLE `penalty_histories` DISABLE KEYS */;
/*!40000 ALTER TABLE `penalty_histories` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `point_exchange_requests`
--

DROP TABLE IF EXISTS `point_exchange_requests`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `point_exchange_requests` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `point_amount` int NOT NULL,
  `cash_amount` decimal(12,2) NOT NULL,
  `status` enum('pending','approved','rejected','paid') NOT NULL,
  `requested_at` datetime NOT NULL,
  `processed_at` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_point_exchange_requests_id` (`id`),
  KEY `ix_px_amount` (`point_amount`),
  KEY `ix_px_user_requested` (`user_id`,`requested_at`),
  KEY `ix_px_status` (`status`),
  CONSTRAINT `point_exchange_requests_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `point_exchange_requests`
--

LOCK TABLES `point_exchange_requests` WRITE;
/*!40000 ALTER TABLE `point_exchange_requests` DISABLE KEYS */;
/*!40000 ALTER TABLE `point_exchange_requests` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `point_histories`
--

DROP TABLE IF EXISTS `point_histories`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `point_histories` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `challenge_id` int DEFAULT NULL,
  `description` varchar(255) NOT NULL,
  `point_amount` int NOT NULL,
  `type` enum('gain','use','refund') NOT NULL,
  `total_earned_point` int DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_ph_challenge` (`challenge_id`),
  KEY `ix_ph_user_created` (`user_id`,`created_at`),
  KEY `ix_ph_amount` (`point_amount`),
  KEY `ix_point_histories_id` (`id`),
  KEY `ix_ph_type` (`type`),
  CONSTRAINT `point_histories_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `point_histories_ibfk_2` FOREIGN KEY (`challenge_id`) REFERENCES `challenges` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `point_histories`
--

LOCK TABLES `point_histories` WRITE;
/*!40000 ALTER TABLE `point_histories` DISABLE KEYS */;
/*!40000 ALTER TABLE `point_histories` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `posts`
--

DROP TABLE IF EXISTS `posts`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `posts` (
  `id` int NOT NULL AUTO_INCREMENT,
  `title` varchar(200) NOT NULL,
  `content` text NOT NULL,
  `user_id` int DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `posts_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `posts`
--

LOCK TABLES `posts` WRITE;
/*!40000 ALTER TABLE `posts` DISABLE KEYS */;
INSERT INTO `posts` VALUES (1,'ì²« ë²ˆì§¸ ê²Œì‹œê¸€','ì•ˆë…•í•˜ì„¸ìš”! ì²« ë²ˆì§¸ ê²Œì‹œê¸€ìž…ë‹ˆë‹¤.',1,'2025-08-13 06:32:20','2025-08-13 06:32:20'),(2,'ë‘ ë²ˆì§¸ ê²Œì‹œê¸€','ë‘ ë²ˆì§¸ ê²Œì‹œê¸€ ë‚´ìš©ìž…ë‹ˆë‹¤.',2,'2025-08-13 06:32:20','2025-08-13 06:32:20');
/*!40000 ALTER TABLE `posts` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `proofs`
--

DROP TABLE IF EXISTS `proofs`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `proofs` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `challenge_id` int NOT NULL,
  `round_id` int NOT NULL,
  `proof_type` varchar(30) NOT NULL,
  `file_url` varchar(255) DEFAULT NULL,
  `exif_data` json DEFAULT NULL,
  `status` enum('pending','approved','rejected') NOT NULL,
  `initial_verified_by` int DEFAULT NULL,
  `submitted_at` datetime NOT NULL,
  `verified_at` datetime DEFAULT NULL,
  `ai_score` float DEFAULT NULL,
  `explanation` text,
  `explanation_choices` varchar(255) DEFAULT NULL,
  `explanation_file_url` varchar(255) DEFAULT NULL,
  `files_json` json DEFAULT NULL,
  `face_compare_score` float DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `initial_verified_by` (`initial_verified_by`),
  KEY `ix_proof_round_user_submitted` (`round_id`,`user_id`,`submitted_at`),
  KEY `ix_proofs_id` (`id`),
  KEY `ix_proof_status` (`status`),
  KEY `ix_proof_challenge` (`challenge_id`),
  CONSTRAINT `proofs_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `proofs_ibfk_2` FOREIGN KEY (`challenge_id`) REFERENCES `challenges` (`id`) ON DELETE CASCADE,
  CONSTRAINT `proofs_ibfk_3` FOREIGN KEY (`round_id`) REFERENCES `challenge_rounds` (`id`) ON DELETE CASCADE,
  CONSTRAINT `proofs_ibfk_4` FOREIGN KEY (`initial_verified_by`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `proofs`
--

LOCK TABLES `proofs` WRITE;
/*!40000 ALTER TABLE `proofs` DISABLE KEYS */;
/*!40000 ALTER TABLE `proofs` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `qrcodes`
--

DROP TABLE IF EXISTS `qrcodes`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `qrcodes` (
  `id` int NOT NULL AUTO_INCREMENT,
  `round_id` int NOT NULL,
  `user_id` int NOT NULL,
  `qr_token` varchar(255) NOT NULL,
  `scanned_at` datetime DEFAULT NULL,
  `expires_at` datetime DEFAULT NULL,
  `jti` varchar(64) DEFAULT NULL,
  `status` enum('valid','used','expired','revoked') NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_qr_user_round` (`user_id`,`round_id`),
  KEY `ix_qrcodes_id` (`id`),
  KEY `ix_qr_user` (`user_id`),
  KEY `ix_qr_round_status` (`round_id`,`status`),
  KEY `ix_qr_token` (`qr_token`),
  CONSTRAINT `qrcodes_ibfk_1` FOREIGN KEY (`round_id`) REFERENCES `challenge_rounds` (`id`) ON DELETE CASCADE,
  CONSTRAINT `qrcodes_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `qrcodes`
--

LOCK TABLES `qrcodes` WRITE;
/*!40000 ALTER TABLE `qrcodes` DISABLE KEYS */;
/*!40000 ALTER TABLE `qrcodes` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `refunds`
--

DROP TABLE IF EXISTS `refunds`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `refunds` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `challenge_id` int NOT NULL,
  `amount` decimal(12,2) NOT NULL,
  `currency` varchar(3) NOT NULL,
  `reason` varchar(100) NOT NULL,
  `processed_at` datetime DEFAULT NULL,
  `refund_status` enum('pending','processing','succeeded','failed') NOT NULL,
  `toss_refund_id` varchar(100) DEFAULT NULL,
  `error_msg` text,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_refund_toss` (`toss_refund_id`),
  KEY `ix_refunds_id` (`id`),
  KEY `ix_refund_user_processed` (`user_id`,`processed_at`),
  KEY `ix_refund_status` (`refund_status`),
  KEY `ix_refund_challenge` (`challenge_id`),
  KEY `ix_refund_amount` (`amount`),
  CONSTRAINT `refunds_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT,
  CONSTRAINT `refunds_ibfk_2` FOREIGN KEY (`challenge_id`) REFERENCES `challenges` (`id`) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `refunds`
--

LOCK TABLES `refunds` WRITE;
/*!40000 ALTER TABLE `refunds` DISABLE KEYS */;
/*!40000 ALTER TABLE `refunds` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `report_proofs`
--

DROP TABLE IF EXISTS `report_proofs`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `report_proofs` (
  `id` int NOT NULL AUTO_INCREMENT,
  `report_id` int NOT NULL,
  `file_url` varchar(255) NOT NULL,
  `uploaded_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_report_proofs_id` (`id`),
  KEY `ix_reportproof_uploaded` (`uploaded_at`),
  KEY `ix_reportproof_report` (`report_id`),
  CONSTRAINT `report_proofs_ibfk_1` FOREIGN KEY (`report_id`) REFERENCES `reports` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `report_proofs`
--

LOCK TABLES `report_proofs` WRITE;
/*!40000 ALTER TABLE `report_proofs` DISABLE KEYS */;
/*!40000 ALTER TABLE `report_proofs` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `reports`
--

DROP TABLE IF EXISTS `reports`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `reports` (
  `id` int NOT NULL AUTO_INCREMENT,
  `reporter_id` int NOT NULL,
  `reported_id` int NOT NULL,
  `challenge_id` int DEFAULT NULL,
  `reason` varchar(255) NOT NULL,
  `details` text,
  `status` enum('pending','under_review','resolved','rejected','cancelled') NOT NULL,
  `is_false_report` tinyint(1) NOT NULL,
  `penalty_given` tinyint(1) NOT NULL,
  `penalty_score` int NOT NULL,
  `is_cancelled` tinyint(1) NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_report_challenge` (`challenge_id`),
  KEY `ix_report_status` (`status`),
  KEY `ix_report_reporter` (`reporter_id`),
  KEY `ix_reports_id` (`id`),
  KEY `ix_report_created` (`created_at`),
  KEY `ix_report_reported` (`reported_id`),
  CONSTRAINT `reports_ibfk_1` FOREIGN KEY (`reporter_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT,
  CONSTRAINT `reports_ibfk_2` FOREIGN KEY (`reported_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT,
  CONSTRAINT `reports_ibfk_3` FOREIGN KEY (`challenge_id`) REFERENCES `challenges` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `reports`
--

LOCK TABLES `reports` WRITE;
/*!40000 ALTER TABLE `reports` DISABLE KEYS */;
/*!40000 ALTER TABLE `reports` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `review_helpfuls`
--

DROP TABLE IF EXISTS `review_helpfuls`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `review_helpfuls` (
  `id` int NOT NULL AUTO_INCREMENT,
  `review_id` int NOT NULL,
  `user_id` int NOT NULL,
  `created_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_helpful_review_user` (`review_id`,`user_id`),
  KEY `ix_review_helpfuls_id` (`id`),
  KEY `ix_helpful_created` (`created_at`),
  KEY `ix_helpful_review` (`review_id`),
  KEY `ix_helpful_user` (`user_id`),
  CONSTRAINT `review_helpfuls_ibfk_1` FOREIGN KEY (`review_id`) REFERENCES `reviews` (`id`) ON DELETE CASCADE,
  CONSTRAINT `review_helpfuls_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `review_helpfuls`
--

LOCK TABLES `review_helpfuls` WRITE;
/*!40000 ALTER TABLE `review_helpfuls` DISABLE KEYS */;
/*!40000 ALTER TABLE `review_helpfuls` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `reviews`
--

DROP TABLE IF EXISTS `reviews`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `reviews` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `challenge_id` int NOT NULL,
  `round_id` int DEFAULT NULL,
  `comment` text,
  `rating` float NOT NULL,
  `helpful_count` int NOT NULL,
  `status` enum('visible','hidden','deleted') NOT NULL,
  `images_json` json DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_review_user_challenge` (`user_id`,`challenge_id`),
  UNIQUE KEY `uq_review_user_round` (`user_id`,`round_id`),
  KEY `ix_review_status` (`status`),
  KEY `ix_review_helpful_count` (`helpful_count`),
  KEY `ix_review_rating` (`rating`),
  KEY `ix_reviews_id` (`id`),
  KEY `ix_review_challenge` (`challenge_id`),
  KEY `ix_review_round` (`round_id`),
  CONSTRAINT `reviews_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `reviews_ibfk_2` FOREIGN KEY (`challenge_id`) REFERENCES `challenges` (`id`) ON DELETE CASCADE,
  CONSTRAINT `reviews_ibfk_3` FOREIGN KEY (`round_id`) REFERENCES `challenge_rounds` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `reviews`
--

LOCK TABLES `reviews` WRITE;
/*!40000 ALTER TABLE `reviews` DISABLE KEYS */;
/*!40000 ALTER TABLE `reviews` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `round_attendances`
--

DROP TABLE IF EXISTS `round_attendances`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `round_attendances` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `round_id` int NOT NULL,
  `is_checked_in` tinyint(1) NOT NULL,
  `is_checked_out` tinyint(1) NOT NULL,
  `checkin_time` datetime DEFAULT NULL,
  `checkout_time` datetime DEFAULT NULL,
  `manually_verified` tinyint(1) NOT NULL,
  `verified_by` int DEFAULT NULL,
  `verified_at` datetime DEFAULT NULL,
  `ai_score` float DEFAULT NULL,
  `qr_id` int DEFAULT NULL,
  `scanned_at` datetime DEFAULT NULL,
  `status` enum('pending','present','late','absent','rejected') NOT NULL,
  `proof_id` int DEFAULT NULL,
  `verified_by_meta` tinyint(1) NOT NULL,
  `meta_check_time` datetime DEFAULT NULL,
  `note` text,
  `check_method` enum('qr','gps','image','manual') NOT NULL,
  `auto_decision` enum('_pass','review','fail') DEFAULT NULL,
  `initial_decision` enum('approved','rejected','review') NOT NULL,
  `initial_decision_reason` text,
  `initial_decision_code` enum('late','no_gps','wrong_place','no_face','file_invalid','other') DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_ra_user_round` (`user_id`,`round_id`),
  KEY `verified_by` (`verified_by`),
  KEY `qr_id` (`qr_id`),
  KEY `proof_id` (`proof_id`),
  KEY `ix_ra_round_user` (`round_id`,`user_id`),
  KEY `ix_ra_status` (`status`),
  KEY `ix_round_attendances_id` (`id`),
  KEY `ix_ra_checkin` (`checkin_time`),
  CONSTRAINT `round_attendances_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `round_attendances_ibfk_2` FOREIGN KEY (`round_id`) REFERENCES `challenge_rounds` (`id`) ON DELETE CASCADE,
  CONSTRAINT `round_attendances_ibfk_3` FOREIGN KEY (`verified_by`) REFERENCES `users` (`id`) ON DELETE SET NULL,
  CONSTRAINT `round_attendances_ibfk_4` FOREIGN KEY (`qr_id`) REFERENCES `qrcodes` (`id`) ON DELETE SET NULL,
  CONSTRAINT `round_attendances_ibfk_5` FOREIGN KEY (`proof_id`) REFERENCES `proofs` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `round_attendances`
--

LOCK TABLES `round_attendances` WRITE;
/*!40000 ALTER TABLE `round_attendances` DISABLE KEYS */;
/*!40000 ALTER TABLE `round_attendances` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `round_pictures`
--

DROP TABLE IF EXISTS `round_pictures`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `round_pictures` (
  `id` int NOT NULL AUTO_INCREMENT,
  `round_id` int NOT NULL,
  `uploaded_by` int DEFAULT NULL,
  `file_url` varchar(255) NOT NULL,
  `is_public` tinyint(1) NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_round_pictures_id` (`id`),
  KEY `ix_roundpic_uploader` (`uploaded_by`),
  KEY `ix_roundpic_round` (`round_id`),
  KEY `ix_roundpic_created` (`created_at`),
  KEY `ix_roundpic_public` (`is_public`),
  CONSTRAINT `round_pictures_ibfk_1` FOREIGN KEY (`round_id`) REFERENCES `challenge_rounds` (`id`) ON DELETE CASCADE,
  CONSTRAINT `round_pictures_ibfk_2` FOREIGN KEY (`uploaded_by`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `round_pictures`
--

LOCK TABLES `round_pictures` WRITE;
/*!40000 ALTER TABLE `round_pictures` DISABLE KEYS */;
/*!40000 ALTER TABLE `round_pictures` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `tag`
--

DROP TABLE IF EXISTS `tag`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `tag` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(50) NOT NULL,
  `is_active` tinyint(1) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `tag`
--

LOCK TABLES `tag` WRITE;
/*!40000 ALTER TABLE `tag` DISABLE KEYS */;
/*!40000 ALTER TABLE `tag` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `tags`
--

DROP TABLE IF EXISTS `tags`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `tags` (
  `id` int NOT NULL AUTO_INCREMENT,
  `tag` varchar(255) NOT NULL,
  `icon_url` varchar(255) DEFAULT NULL,
  `is_active` tinyint(1) NOT NULL,
  `embedding` json DEFAULT NULL,
  `embedding_model` varchar(100) DEFAULT NULL,
  `embedding_updated_at` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `tag` (`tag`),
  KEY `ix_tags_id` (`id`),
  KEY `ix_tag_active` (`is_active`),
  KEY `ix_tag_text` (`tag`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `tags`
--

LOCK TABLES `tags` WRITE;
/*!40000 ALTER TABLE `tags` DISABLE KEYS */;
/*!40000 ALTER TABLE `tags` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `user_tag`
--

DROP TABLE IF EXISTS `user_tag`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `user_tag` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `tag_id` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_user_tag` (`user_id`,`tag_id`),
  KEY `tag_id` (`tag_id`),
  CONSTRAINT `user_tag_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `user_tag_ibfk_2` FOREIGN KEY (`tag_id`) REFERENCES `tags` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `user_tag`
--

LOCK TABLES `user_tag` WRITE;
/*!40000 ALTER TABLE `user_tag` DISABLE KEYS */;
/*!40000 ALTER TABLE `user_tag` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `user_tags`
--

DROP TABLE IF EXISTS `user_tags`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `user_tags` (
  `id` int NOT NULL AUTO_INCREMENT,
  `tag_id` int NOT NULL,
  `user_id` int NOT NULL,
  `selected_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_user_tag_pair` (`tag_id`,`user_id`),
  KEY `ix_user_tag_user` (`user_id`),
  KEY `ix_user_tags_id` (`id`),
  KEY `ix_user_tag_tag` (`tag_id`),
  CONSTRAINT `user_tags_ibfk_1` FOREIGN KEY (`tag_id`) REFERENCES `tags` (`id`) ON DELETE CASCADE,
  CONSTRAINT `user_tags_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `user_tags`
--

LOCK TABLES `user_tags` WRITE;
/*!40000 ALTER TABLE `user_tags` DISABLE KEYS */;
/*!40000 ALTER TABLE `user_tags` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `users`
--

DROP TABLE IF EXISTS `users`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `users` (
  `id` int NOT NULL AUTO_INCREMENT,
  `username` varchar(50) NOT NULL,
  `email` varchar(100) NOT NULL,
  `password_hash` varchar(255) NOT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`),
  UNIQUE KEY `email` (`email`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `users`
--

LOCK TABLES `users` WRITE;
/*!40000 ALTER TABLE `users` DISABLE KEYS */;
INSERT INTO `users` VALUES (1,'admin','admin@example.com','$2b$10$example.hash.for.testing','2025-08-13 06:32:20','2025-08-13 06:32:20'),(2,'testuser','test@example.com','$2b$10$example.hash.for.testing','2025-08-13 06:32:20','2025-08-13 06:32:20');
/*!40000 ALTER TABLE `users` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2025-08-18 15:29:45
