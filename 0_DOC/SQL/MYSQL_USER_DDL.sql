CREATE TABLE `userinfo` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT COMMENT '用户唯一标识',
  `username` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '用户登录账号',
  `password` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '加密后的密码',
  `showname` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT '' COMMENT '用户昵称',
  `age` tinyint unsigned DEFAULT NULL COMMENT '用户年龄',
  `address` varchar(200) COLLATE utf8mb4_unicode_ci DEFAULT '' COMMENT '用户联系地址',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `phone` varchar(11) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '联系人手机号',
  `role` varchar(10) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '用户角色,包括admin,user',
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_username` (`username`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO oneapi.userinfo (username,password,showname,age,address,created_at,updated_at,phone,`role`) VALUES
	 ('admin','123','d2bed1d3',18,'City941 Rd.','2025-08-07 02:20:54.0','2025-08-13 01:22:38.0','13888888888','admin'),
	 ('user','123','7ab50295',44,'Town645 Ave.','2025-08-07 02:20:54.0','2025-08-13 01:22:39.0','15999999999','user');
