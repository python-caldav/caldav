-- Create users table for SOGo authentication
-- SOGo will auto-create its own internal tables (sogo_user_profile, sogo_folder_info, etc.)

CREATE TABLE IF NOT EXISTS sogo_users (
  c_uid VARCHAR(256) NOT NULL PRIMARY KEY,
  c_name VARCHAR(256),
  c_password VARCHAR(256),
  c_cn VARCHAR(256),
  mail VARCHAR(256)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Insert test user with MD5-hashed password
-- Password: testpass (MD5 hash required by SOGo with md5 algorithm)
INSERT INTO sogo_users (c_uid, c_name, c_password, c_cn, mail)
VALUES ('testuser', 'testuser', MD5('testpass'), 'Test User', 'testuser@example.com')
ON DUPLICATE KEY UPDATE c_password=MD5('testpass');
