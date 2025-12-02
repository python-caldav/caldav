-- Create SOGo tables and test user

-- User profile table
CREATE TABLE IF NOT EXISTS sogo_user_profile (
  c_uid VARCHAR(256) NOT NULL PRIMARY KEY,
  c_defaults TEXT,
  c_settings TEXT
);

-- Folder info table
CREATE TABLE IF NOT EXISTS sogo_folder_info (
  c_folder_id SERIAL PRIMARY KEY,
  c_path VARCHAR(255) NOT NULL,
  c_path1 VARCHAR(255),
  c_path2 VARCHAR(255),
  c_path3 VARCHAR(255),
  c_path4 VARCHAR(255),
  c_foldername VARCHAR(255) NOT NULL,
  c_location VARCHAR(2048) NOT NULL,
  c_quick_location VARCHAR(2048),
  c_acl_location VARCHAR(2048),
  c_folder_type VARCHAR(255) NOT NULL
);

CREATE INDEX IF NOT EXISTS sogo_folder_info_path_idx ON sogo_folder_info(c_path);

-- Sessions folder table
CREATE TABLE IF NOT EXISTS sogo_sessions_folder (
  c_id VARCHAR(255) PRIMARY KEY,
  c_value VARCHAR(255) NOT NULL,
  c_creationdate INT NOT NULL,
  c_lastseen INT NOT NULL
);

-- Email alarms table
CREATE TABLE IF NOT EXISTS sogo_alarms_folder (
  c_path VARCHAR(255) NOT NULL,
  c_name VARCHAR(255) NOT NULL,
  c_uid VARCHAR(255) NOT NULL,
  c_recurrence_id INT,
  c_alarm_number INT NOT NULL,
  c_alarm_date INT NOT NULL
);

-- ACL (Access Control List) table
CREATE TABLE IF NOT EXISTS sogo_acl (
  c_folder_id INT NOT NULL,
  c_object VARCHAR(255) NOT NULL,
  c_uid VARCHAR(255) NOT NULL,
  c_role VARCHAR(80) NOT NULL
);

CREATE INDEX IF NOT EXISTS sogo_acl_folder_idx ON sogo_acl(c_folder_id);
CREATE INDEX IF NOT EXISTS sogo_acl_uid_idx ON sogo_acl(c_uid);

-- Users table for authentication
CREATE TABLE IF NOT EXISTS sogo_users (
  c_uid VARCHAR(256) NOT NULL PRIMARY KEY,
  c_name VARCHAR(256),
  c_password VARCHAR(256),
  c_cn VARCHAR(256),
  mail VARCHAR(256)
);

-- Insert test user (password: testpass, MD5 hashed)
-- MD5 hash of 'testpass' is '179ad45c6ce2cb97cf1029e212046e81'
INSERT INTO sogo_users (c_uid, c_name, c_password, c_cn, mail)
VALUES ('testuser', 'testuser', '179ad45c6ce2cb97cf1029e212046e81', 'Test User', 'testuser@example.com')
ON CONFLICT (c_uid) DO NOTHING;
