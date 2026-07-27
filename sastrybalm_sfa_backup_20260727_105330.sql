-- ========================================================
-- Safar SFA Enterprise SQL Database Backup
-- Generated At: 2026-07-27 10:53:30
-- Database Engine: MySQL / MariaDB
-- Software Version: Safar SFA v2.0 Enterprise
-- ========================================================

SET FOREIGN_KEY_CHECKS=0;
SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
SET time_zone = "+00:00";

-- --------------------------------------------------------
-- Table structure for table `geographies`
-- --------------------------------------------------------
DROP TABLE IF EXISTS `geographies`;
CREATE TABLE `geographies` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `code` varchar(100) NOT NULL,
  `level` enum('zone','region','territory') NOT NULL,
  `parent_id` int DEFAULT NULL,
  `erp_id` varchar(100) DEFAULT NULL,
  `is_active` tinyint(1) NOT NULL,
  `created_at` datetime DEFAULT (now()),
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_geographies_code` (`code`),
  KEY `parent_id` (`parent_id`),
  KEY `ix_geographies_id` (`id`),
  CONSTRAINT `geographies_ibfk_1` FOREIGN KEY (`parent_id`) REFERENCES `geographies` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Dumping data for table `geographies`
INSERT INTO `geographies` (`id`, `name`, `code`, `level`, `parent_id`, `erp_id`, `is_active`, `created_at`) VALUES
(1, 'SOUTH INDIA', 'SOUTH-IND', 'zone', NULL, NULL, 1, '2026-07-25 06:41:51'),
(2, 'NORTH TN', 'NORTH-TN', 'region', 1, NULL, 1, '2026-07-25 06:42:23'),
(3, 'CHENNAI TN', 'TN-CHN', 'territory', 2, NULL, 1, '2026-07-25 06:42:50'),
(4, 'ODISHA', 'OD', 'region', 1, NULL, 1, '2026-07-25 09:44:17'),
(5, 'BHUBANESWAR ODISHA', 'OD-BBNSR', 'territory', 4, NULL, 1, '2026-07-25 09:44:56');

-- --------------------------------------------------------
-- Table structure for table `company_profiles`
-- --------------------------------------------------------
DROP TABLE IF EXISTS `company_profiles`;
CREATE TABLE `company_profiles` (
  `id` int NOT NULL AUTO_INCREMENT,
  `code` varchar(100) NOT NULL,
  `name` varchar(255) NOT NULL,
  `zap_base_url` varchar(500) DEFAULT NULL,
  `zap_api_key_encrypted` text,
  `zap_backend_company` varchar(255) DEFAULT NULL,
  `cmms_base_url` varchar(500) DEFAULT NULL,
  `cmms_api_key_encrypted` text,
  `cmms_backend_company` varchar(255) DEFAULT NULL,
  `connect_base_url` varchar(500) DEFAULT NULL,
  `connect_api_key_encrypted` text,
  `connect_backend_company` varchar(255) DEFAULT NULL,
  `tags` text,
  `is_active` tinyint(1) NOT NULL,
  `created_at` datetime DEFAULT (now()),
  `updated_at` datetime DEFAULT (now()),
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_company_profiles_code` (`code`),
  KEY `ix_company_profiles_id` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --------------------------------------------------------
-- Table structure for table `system_configuration`
-- --------------------------------------------------------
DROP TABLE IF EXISTS `system_configuration`;
CREATE TABLE `system_configuration` (
  `id` int NOT NULL,
  `gps_threshold_metres` int NOT NULL,
  `sync_interval_seconds` int NOT NULL,
  `flag_gps_distance_metres` int NOT NULL,
  `flag_min_visit_seconds` int NOT NULL,
  `payment_mode` enum('cash_only','online_only','cash_and_online') DEFAULT NULL,
  `denomination_mandatory` tinyint(1) NOT NULL,
  `auto_approval_cutoff_hours` int NOT NULL,
  `s3_is_enabled` tinyint(1) NOT NULL,
  `s3_endpoint_url` varchar(255) DEFAULT NULL,
  `s3_bucket_name` varchar(255) DEFAULT NULL,
  `s3_access_key_id` varchar(255) DEFAULT NULL,
  `s3_secret_access_key` text,
  `s3_region_name` varchar(100) DEFAULT NULL,
  `s3_public_url_prefix` varchar(255) DEFAULT NULL,
  `s3_files_is_enabled` tinyint(1) NOT NULL,
  `s3_files_endpoint_url` varchar(255) DEFAULT NULL,
  `s3_files_bucket_name` varchar(255) DEFAULT NULL,
  `s3_files_access_key_id` varchar(255) DEFAULT NULL,
  `s3_files_secret_access_key` text,
  `s3_files_region_name` varchar(100) DEFAULT NULL,
  `s3_files_public_url_prefix` varchar(255) DEFAULT NULL,
  `whatsapp_api_key` text,
  `whatsapp_phone_number_id` varchar(255) DEFAULT NULL,
  `whatsapp_business_account_id` varchar(255) DEFAULT NULL,
  `whatsapp_is_enabled` tinyint(1) NOT NULL,
  `updated_at` datetime DEFAULT (now()),
  `smtp_host` varchar(255) DEFAULT NULL,
  `smtp_port` int NOT NULL DEFAULT '587',
  `smtp_user` varchar(255) DEFAULT NULL,
  `smtp_password` text,
  `smtp_from` varchar(255) DEFAULT NULL,
  `smtp_use_tls` tinyint(1) NOT NULL DEFAULT '1',
  `archival_retention_days` int NOT NULL DEFAULT '90',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Dumping data for table `system_configuration`
INSERT INTO `system_configuration` (`id`, `gps_threshold_metres`, `sync_interval_seconds`, `flag_gps_distance_metres`, `flag_min_visit_seconds`, `payment_mode`, `denomination_mandatory`, `auto_approval_cutoff_hours`, `s3_is_enabled`, `s3_endpoint_url`, `s3_bucket_name`, `s3_access_key_id`, `s3_secret_access_key`, `s3_region_name`, `s3_public_url_prefix`, `s3_files_is_enabled`, `s3_files_endpoint_url`, `s3_files_bucket_name`, `s3_files_access_key_id`, `s3_files_secret_access_key`, `s3_files_region_name`, `s3_files_public_url_prefix`, `whatsapp_api_key`, `whatsapp_phone_number_id`, `whatsapp_business_account_id`, `whatsapp_is_enabled`, `updated_at`, `smtp_host`, `smtp_port`, `smtp_user`, `smtp_password`, `smtp_from`, `smtp_use_tls`, `archival_retention_days`) VALUES
(1, 0, 0, 0, 0, NULL, 0, 0, 1, 'https://s3.us-east-005.backblazeb2.com', 'sb-sfa-dev', '0051de3245a6d20000000000b', 'gAAAAABqZwizUy4gO3LJKFhs9LJ_VZ5oDxnz8GvTeidL_qAybuAupZ9Y_cbaFY-0uLG3hBH8wRasl-e7PHzJ-Dk0YRdpMpmMcRXD0T8TOV-FQMPWw9I__X0=', 'us-east-005', NULL, 0, 'https://s3.us-east-005.backblazeb2.com', 'sb-sfa-dev', '0051de3245a6d20000000000b', 'gAAAAABqZwizEyZn3Ft_1U4B0_hYOkPUW2yCQeEzZdkb5fdUgNDsqNR6AP0xk--N9USq8J4GyUU3-wVG9AEAxBayiEGlOran4yB9ZFWCTHim-7slvWjU4Q8=', 'us-east-005', NULL, NULL, NULL, NULL, 0, '2026-07-27 07:28:51', NULL, 587, NULL, NULL, NULL, 1, 90);

-- --------------------------------------------------------
-- Table structure for table `warehouses`
-- --------------------------------------------------------
DROP TABLE IF EXISTS `warehouses`;
CREATE TABLE `warehouses` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `code` varchar(100) NOT NULL,
  `pincode` varchar(10) DEFAULT NULL,
  `address` varchar(500) DEFAULT NULL,
  `contact_person` varchar(255) DEFAULT NULL,
  `mobile` varchar(20) DEFAULT NULL,
  `is_active` tinyint(1) NOT NULL,
  `created_at` datetime NOT NULL,
  `geography_id` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_warehouses_code` (`code`),
  KEY `ix_warehouses_id` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Dumping data for table `warehouses`
INSERT INTO `warehouses` (`id`, `name`, `code`, `pincode`, `address`, `contact_person`, `mobile`, `is_active`, `created_at`, `geography_id`) VALUES
(2, 'NORTH TN WAREHOUSE', 'TN-NRTH-WAREHOUSE', '600128', NULL, NULL, NULL, 1, '2026-07-25 08:30:28', 2),
(3, 'TN COIMBATORE', 'TN-CMBR-WAREHOUSE', '608001', NULL, NULL, NULL, 1, '2026-07-25 08:31:05', NULL);

-- --------------------------------------------------------
-- Table structure for table `product_alias_maps`
-- --------------------------------------------------------
DROP TABLE IF EXISTS `product_alias_maps`;
CREATE TABLE `product_alias_maps` (
  `id` int NOT NULL AUTO_INCREMENT,
  `company_profile_id` int NOT NULL,
  `product_id` int NOT NULL,
  `zap_item_code` varchar(100) DEFAULT NULL,
  `cmms_item_code` varchar(100) DEFAULT NULL,
  `connect_item_code` varchar(100) DEFAULT NULL,
  `conversion_factor` decimal(10,5) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_product_alias_maps_product_id` (`product_id`),
  KEY `ix_product_alias_maps_company_profile_id` (`company_profile_id`),
  CONSTRAINT `product_alias_maps_ibfk_1` FOREIGN KEY (`company_profile_id`) REFERENCES `company_profiles` (`id`) ON DELETE CASCADE,
  CONSTRAINT `product_alias_maps_ibfk_2` FOREIGN KEY (`product_id`) REFERENCES `products` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --------------------------------------------------------
-- Table structure for table `account_alias_maps`
-- --------------------------------------------------------
DROP TABLE IF EXISTS `account_alias_maps`;
CREATE TABLE `account_alias_maps` (
  `id` int NOT NULL AUTO_INCREMENT,
  `company_profile_id` int NOT NULL,
  `account_name` varchar(255) NOT NULL,
  `account_type` varchar(50) DEFAULT NULL,
  `zap_account_code` varchar(100) DEFAULT NULL,
  `cmms_account_code` varchar(100) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_account_alias_maps_company_profile_id` (`company_profile_id`),
  CONSTRAINT `account_alias_maps_ibfk_1` FOREIGN KEY (`company_profile_id`) REFERENCES `company_profiles` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --------------------------------------------------------
-- Table structure for table `product_warehouse_stocks`
-- --------------------------------------------------------
DROP TABLE IF EXISTS `product_warehouse_stocks`;
CREATE TABLE `product_warehouse_stocks` (
  `id` int NOT NULL AUTO_INCREMENT,
  `product_id` int NOT NULL,
  `warehouse_id` int NOT NULL,
  `warehouse_location` varchar(100) DEFAULT NULL,
  `stock_qty` int NOT NULL,
  `reorder_level` int NOT NULL,
  `is_active` tinyint(1) NOT NULL,
  `created_at` datetime DEFAULT (now()),
  `updated_at` datetime DEFAULT (now()),
  PRIMARY KEY (`id`),
  KEY `ix_product_warehouse_stocks_warehouse_id` (`warehouse_id`),
  KEY `ix_product_warehouse_stocks_product_id` (`product_id`),
  KEY `ix_product_warehouse_stocks_id` (`id`),
  CONSTRAINT `product_warehouse_stocks_ibfk_1` FOREIGN KEY (`product_id`) REFERENCES `products` (`id`) ON DELETE CASCADE,
  CONSTRAINT `product_warehouse_stocks_ibfk_2` FOREIGN KEY (`warehouse_id`) REFERENCES `warehouses` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Dumping data for table `product_warehouse_stocks`
INSERT INTO `product_warehouse_stocks` (`id`, `product_id`, `warehouse_id`, `warehouse_location`, `stock_qty`, `reorder_level`, `is_active`, `created_at`, `updated_at`) VALUES
(1, 3, 3, NULL, 0, 10, 1, '2026-07-25 10:28:22', '2026-07-25 10:28:22'),
(2, 3, 2, NULL, 45, 10, 1, '2026-07-25 10:28:22', '2026-07-26 12:27:00'),
(3, 5, 2, NULL, 0, 10, 1, '2026-07-25 10:28:43', '2026-07-25 10:28:43'),
(4, 5, 3, NULL, 0, 10, 1, '2026-07-25 10:29:12', '2026-07-25 10:29:12');

-- --------------------------------------------------------
-- Table structure for table `products`
-- --------------------------------------------------------
DROP TABLE IF EXISTS `products`;
CREATE TABLE `products` (
  `id` int NOT NULL AUTO_INCREMENT,
  `erp_id` varchar(100) DEFAULT NULL,
  `sku` varchar(100) DEFAULT NULL,
  `name` varchar(255) NOT NULL,
  `division` varchar(100) DEFAULT NULL,
  `category_type` enum('Sales','Marketing - Procurement','Marketing - Stock') NOT NULL,
  `primary_category` varchar(100) DEFAULT NULL,
  `secondary_category` varchar(100) DEFAULT NULL,
  `mrp` decimal(10,2) DEFAULT NULL,
  `unit_cost` decimal(10,2) DEFAULT NULL,
  `stock_qty` int NOT NULL,
  `reorder_level` int NOT NULL,
  `warehouse_id` int DEFAULT NULL,
  `warehouse_location` varchar(100) DEFAULT NULL,
  `gst_rate` decimal(5,2) DEFAULT NULL,
  `must_sell` tinyint(1) NOT NULL,
  `is_active` tinyint(1) NOT NULL,
  `created_at` datetime DEFAULT (now()),
  `updated_at` datetime DEFAULT (now()),
  `company_profile_id` int DEFAULT NULL,
  `is_stockable` tinyint(1) NOT NULL DEFAULT '1',
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_products_sku` (`sku`),
  UNIQUE KEY `ix_products_erp_id` (`erp_id`),
  KEY `ix_products_warehouse_id` (`warehouse_id`),
  KEY `ix_products_id` (`id`),
  KEY `fk_product_company` (`company_profile_id`),
  CONSTRAINT `fk_product_company` FOREIGN KEY (`company_profile_id`) REFERENCES `company_profiles` (`id`) ON DELETE SET NULL,
  CONSTRAINT `products_ibfk_1` FOREIGN KEY (`warehouse_id`) REFERENCES `warehouses` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Dumping data for table `products`
INSERT INTO `products` (`id`, `erp_id`, `sku`, `name`, `division`, `category_type`, `primary_category`, `secondary_category`, `mrp`, `unit_cost`, `stock_qty`, `reorder_level`, `warehouse_id`, `warehouse_location`, `gst_rate`, `must_sell`, `is_active`, `created_at`, `updated_at`, `company_profile_id`, `is_stockable`) VALUES
(1, NULL, 'SASB-5INR', 'Safar 5 INR SACHET', NULL, 'Sales', NULL, NULL, 5.00, 4.30, 0, 10, NULL, NULL, 5.00, 0, 1, '2026-07-25 08:09:17', '2026-07-25 08:09:17', NULL, 0),
(2, NULL, 'SASB-50INR', 'Safar 50 INR GLASS BOTTLE', NULL, 'Sales', NULL, NULL, 50.00, 43.00, 0, 10, NULL, NULL, 5.00, 0, 1, '2026-07-25 08:10:15', '2026-07-25 08:10:27', NULL, 0),
(3, NULL, 'BACKLIT-BOARD', 'BACKLIT BOARD', NULL, 'Marketing - Procurement', NULL, NULL, 0.00, 0.00, 45, 10, 3, NULL, 18.00, 0, 1, '2026-07-25 08:17:41', '2026-07-26 12:27:00', NULL, 1),
(4, NULL, 'FRONTLIT-BOARD', 'FRONTLIT BOARD', NULL, 'Marketing - Procurement', NULL, NULL, 0.00, 0.00, 0, 10, NULL, NULL, 18.00, 0, 1, '2026-07-25 08:20:17', '2026-07-25 08:20:17', NULL, 1),
(5, NULL, 'DANGLER-001', 'DANGLERS', NULL, 'Marketing - Stock', NULL, NULL, 0.00, 0.00, 0, 10, NULL, NULL, 18.00, 0, 1, '2026-07-25 08:20:45', '2026-07-25 10:29:12', NULL, 1);

-- --------------------------------------------------------
-- Table structure for table `vendor_products`
-- --------------------------------------------------------
DROP TABLE IF EXISTS `vendor_products`;
CREATE TABLE `vendor_products` (
  `vendor_id` int NOT NULL,
  `product_id` int NOT NULL,
  PRIMARY KEY (`vendor_id`,`product_id`),
  KEY `product_id` (`product_id`),
  CONSTRAINT `vendor_products_ibfk_1` FOREIGN KEY (`vendor_id`) REFERENCES `vendors` (`id`) ON DELETE CASCADE,
  CONSTRAINT `vendor_products_ibfk_2` FOREIGN KEY (`product_id`) REFERENCES `products` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Dumping data for table `vendor_products`
INSERT INTO `vendor_products` (`vendor_id`, `product_id`) VALUES
(1, 3),
(1, 4);

-- --------------------------------------------------------
-- Table structure for table `vendors`
-- --------------------------------------------------------
DROP TABLE IF EXISTS `vendors`;
CREATE TABLE `vendors` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `contact_person` varchar(255) DEFAULT NULL,
  `mobile` varchar(20) DEFAULT NULL,
  `email` varchar(255) DEFAULT NULL,
  `category` varchar(100) DEFAULT NULL,
  `status` enum('active','inactive') NOT NULL,
  `cmms_supplier_ref` varchar(100) DEFAULT NULL,
  `hashed_password` varchar(255) DEFAULT NULL,
  `address` text,
  `created_at` datetime DEFAULT (now()),
  `updated_at` datetime DEFAULT (now()),
  `geography_id` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `mobile` (`mobile`),
  UNIQUE KEY `email` (`email`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Dumping data for table `vendors`
INSERT INTO `vendors` (`id`, `name`, `contact_person`, `mobile`, `email`, `category`, `status`, `cmms_supplier_ref`, `hashed_password`, `address`, `created_at`, `updated_at`, `geography_id`) VALUES
(1, 'G & JC Signage', NULL, NULL, NULL, 'Signage', 'active', NULL, NULL, NULL, '2026-07-25 07:59:11', '2026-07-25 13:38:41', 2);

-- --------------------------------------------------------
-- Table structure for table `vendor_employees`
-- --------------------------------------------------------
DROP TABLE IF EXISTS `vendor_employees`;
CREATE TABLE `vendor_employees` (
  `id` int NOT NULL AUTO_INCREMENT,
  `vendor_id` int NOT NULL,
  `name` varchar(255) NOT NULL,
  `mobile` varchar(20) DEFAULT NULL,
  `email` varchar(255) DEFAULT NULL,
  `cmms_ref` varchar(100) DEFAULT NULL,
  `is_active` tinyint(1) NOT NULL,
  `hashed_password` varchar(255) DEFAULT NULL,
  `created_at` datetime DEFAULT (now()),
  PRIMARY KEY (`id`),
  UNIQUE KEY `mobile` (`mobile`),
  KEY `vendor_id` (`vendor_id`),
  CONSTRAINT `vendor_employees_ibfk_1` FOREIGN KEY (`vendor_id`) REFERENCES `vendors` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --------------------------------------------------------
-- Table structure for table `user_positions`
-- --------------------------------------------------------
DROP TABLE IF EXISTS `user_positions`;
CREATE TABLE `user_positions` (
  `user_id` int NOT NULL,
  `position_id` int NOT NULL,
  PRIMARY KEY (`user_id`,`position_id`),
  KEY `position_id` (`position_id`),
  CONSTRAINT `user_positions_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `user_positions_ibfk_2` FOREIGN KEY (`position_id`) REFERENCES `positions` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Dumping data for table `user_positions`
INSERT INTO `user_positions` (`user_id`, `position_id`) VALUES
(5, 1),
(2, 2),
(3, 3),
(4, 4);

-- --------------------------------------------------------
-- Table structure for table `user_vendors`
-- --------------------------------------------------------
DROP TABLE IF EXISTS `user_vendors`;
CREATE TABLE `user_vendors` (
  `user_id` int NOT NULL,
  `vendor_id` int NOT NULL,
  PRIMARY KEY (`user_id`,`vendor_id`),
  KEY `vendor_id` (`vendor_id`),
  CONSTRAINT `user_vendors_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `user_vendors_ibfk_2` FOREIGN KEY (`vendor_id`) REFERENCES `vendors` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --------------------------------------------------------
-- Table structure for table `user_warehouses`
-- --------------------------------------------------------
DROP TABLE IF EXISTS `user_warehouses`;
CREATE TABLE `user_warehouses` (
  `user_id` int NOT NULL,
  `warehouse_id` int NOT NULL,
  PRIMARY KEY (`user_id`,`warehouse_id`),
  KEY `warehouse_id` (`warehouse_id`),
  CONSTRAINT `user_warehouses_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `user_warehouses_ibfk_2` FOREIGN KEY (`warehouse_id`) REFERENCES `warehouses` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --------------------------------------------------------
-- Table structure for table `users`
-- --------------------------------------------------------
DROP TABLE IF EXISTS `users`;
CREATE TABLE `users` (
  `id` int NOT NULL AUTO_INCREMENT,
  `email` varchar(255) NOT NULL,
  `username` varchar(100) NOT NULL,
  `full_name` varchar(255) NOT NULL,
  `hashed_password` varchar(255) NOT NULL,
  `role` varchar(50) NOT NULL DEFAULT 'field_rep',
  `is_active` tinyint(1) NOT NULL,
  `employee_id` varchar(100) DEFAULT NULL,
  `phone` varchar(20) DEFAULT NULL,
  `imei` varchar(50) DEFAULT NULL,
  `activation_code` varchar(10) DEFAULT NULL,
  `is_registered` tinyint(1) NOT NULL,
  `company_profile_id` int DEFAULT NULL,
  `payment_mode` enum('cash_only','online_only','cash_and_online') DEFAULT NULL,
  `denomination_mandatory` tinyint(1) NOT NULL,
  `created_at` datetime DEFAULT (now()),
  `updated_at` datetime DEFAULT (now()),
  `geography_id` int DEFAULT NULL,
  `vendor_id` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_users_email` (`email`),
  UNIQUE KEY `ix_users_username` (`username`),
  UNIQUE KEY `phone` (`phone`),
  KEY `company_profile_id` (`company_profile_id`),
  KEY `ix_users_id` (`id`),
  CONSTRAINT `users_ibfk_1` FOREIGN KEY (`company_profile_id`) REFERENCES `company_profiles` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Dumping data for table `users`
INSERT INTO `users` (`id`, `email`, `username`, `full_name`, `hashed_password`, `role`, `is_active`, `employee_id`, `phone`, `imei`, `activation_code`, `is_registered`, `company_profile_id`, `payment_mode`, `denomination_mandatory`, `created_at`, `updated_at`, `geography_id`, `vendor_id`) VALUES
(1, 'admin@sravie.in', 'admin', 'System Administrator', '$2b$12$OtiATmeDs5PDdiy6rAyPZuwA.LpHdP6QAhEmxq1A./JDtWiL0lkrW', 'admin', 1, NULL, '9999999999', NULL, NULL, 0, NULL, NULL, 0, '2026-07-24 13:54:16', '2026-07-25 13:03:51', NULL, NULL),
(2, 'kkalpanamuthu10@gmail.com', 'kkalpanamuthu', 'Kalpana Muthu', '$2b$12$IAJ9PnWBVW37ydcX1aAR7eKbSK3BN9ku8uoUx/g340cZYjeBMyClG', 'territory_manager', 1, NULL, '8248207671', NULL, NULL, 0, NULL, NULL, 0, '2026-07-25 07:51:34', '2026-07-25 07:51:34', 2, NULL),
(3, 'kuppri.mohan@gmail.com', 'kuppri.mohan', 'Mohan Kuppiri', '$2b$12$RehNy7arFRzDRmNgd8yfu..WUNM5ghg.v0xWWg6a4K3TjNOL866vy', 'territory_manager', 1, NULL, '9837429742', NULL, NULL, 0, NULL, NULL, 0, '2026-07-27 08:43:17', '2026-07-27 08:43:17', 3, NULL),
(4, 'arasu.tiruvallur@sravie.in', 'arasu.tiruvallur', 'Arasu Tiruvallur', '$2b$12$ONbRthZGCbvJkONHKn5bp.qqyhAsdNE11Qqz.y0L83KSCKKQhZxAO', 'field_rep', 1, NULL, '9038249034', NULL, NULL, 0, NULL, NULL, 0, '2026-07-27 08:44:02', '2026-07-27 08:44:02', NULL, NULL),
(5, 'vinodkumarkolli@gmail.com', 'vinodkumarkolli', 'Vinod Kumar Kolli', '$2b$12$gLTWxHcqkBAJ.X.qvzb/p..eXgOBudHSGnNj/yfRl0wtckQuQ.mvq', 'territory_manager', 1, NULL, '9701881033', NULL, NULL, 0, NULL, NULL, 0, '2026-07-27 09:07:35', '2026-07-27 09:07:35', 1, NULL);

-- --------------------------------------------------------
-- Table structure for table `user_module_access`
-- --------------------------------------------------------
DROP TABLE IF EXISTS `user_module_access`;
CREATE TABLE `user_module_access` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `module` enum('orders','inventory','expenses','timesheets','attendance','visits','gps_map','analytics','approvals','settings','backup','invoicing') NOT NULL,
  `is_active` tinyint(1) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `user_id` (`user_id`,`module`),
  CONSTRAINT `user_module_access_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=45 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Dumping data for table `user_module_access`
INSERT INTO `user_module_access` (`id`, `user_id`, `module`, `is_active`) VALUES
(10, 3, 'orders', 1),
(11, 3, 'inventory', 1),
(12, 3, 'expenses', 1),
(13, 3, 'timesheets', 1),
(14, 3, 'attendance', 1),
(15, 3, 'visits', 1),
(16, 3, 'gps_map', 1),
(17, 3, 'analytics', 1),
(18, 3, 'approvals', 1),
(19, 4, 'orders', 1),
(20, 4, 'inventory', 1),
(21, 4, 'expenses', 1),
(22, 4, 'timesheets', 1),
(23, 4, 'attendance', 1),
(24, 4, 'visits', 1),
(25, 4, 'gps_map', 1),
(26, 4, 'analytics', 1),
(27, 4, 'approvals', 1),
(28, 5, 'orders', 1),
(29, 5, 'inventory', 1),
(30, 5, 'expenses', 1),
(31, 5, 'timesheets', 1),
(32, 5, 'attendance', 1),
(33, 5, 'visits', 1),
(34, 5, 'gps_map', 1),
(35, 5, 'analytics', 1),
(36, 5, 'approvals', 1),
(37, 2, 'orders', 1),
(38, 2, 'inventory', 1),
(39, 2, 'expenses', 1),
(40, 2, 'timesheets', 1),
(41, 2, 'attendance', 1),
(42, 2, 'visits', 1),
(43, 2, 'gps_map', 1),
(44, 2, 'approvals', 1);

-- --------------------------------------------------------
-- Table structure for table `position_beats`
-- --------------------------------------------------------
DROP TABLE IF EXISTS `position_beats`;
CREATE TABLE `position_beats` (
  `position_id` int NOT NULL,
  `beat_id` int NOT NULL,
  PRIMARY KEY (`position_id`,`beat_id`),
  KEY `beat_id` (`beat_id`),
  CONSTRAINT `position_beats_ibfk_1` FOREIGN KEY (`position_id`) REFERENCES `positions` (`id`),
  CONSTRAINT `position_beats_ibfk_2` FOREIGN KEY (`beat_id`) REFERENCES `beats` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Dumping data for table `position_beats`
INSERT INTO `position_beats` (`position_id`, `beat_id`) VALUES
(7, 2);

-- --------------------------------------------------------
-- Table structure for table `positions`
-- --------------------------------------------------------
DROP TABLE IF EXISTS `positions`;
CREATE TABLE `positions` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `code` varchar(100) NOT NULL,
  `level` enum('L1','L2','L3','L4') NOT NULL,
  `reporting_to_id` int DEFAULT NULL,
  `is_active` tinyint(1) NOT NULL,
  `created_at` datetime DEFAULT (now()),
  `warehouse_id` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_positions_code` (`code`),
  KEY `ix_positions_id` (`id`),
  KEY `fk_position_reporting` (`reporting_to_id`),
  CONSTRAINT `fk_position_reporting` FOREIGN KEY (`reporting_to_id`) REFERENCES `positions` (`id`) ON DELETE SET NULL,
  CONSTRAINT `positions_ibfk_1` FOREIGN KEY (`reporting_to_id`) REFERENCES `positions` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=8 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Dumping data for table `positions`
INSERT INTO `positions` (`id`, `name`, `code`, `level`, `reporting_to_id`, `is_active`, `created_at`, `warehouse_id`) VALUES
(1, 'ZSM SOUTH INDIA', 'ZSM-STH-IND', 'L4', NULL, 1, '2026-07-25 06:44:34', NULL),
(2, 'TN CHENNAI RSM', 'RSM-TN-CHN', 'L3', 1, 1, '2026-07-25 06:45:11', NULL),
(3, 'SOUTH CHENNAI ASM', 'ASM-STH-CHN', 'L2', 2, 1, '2026-07-25 06:45:39', NULL),
(4, 'SOUTH CHN L1', 'L1-STH-CHN', 'L1', 3, 1, '2026-07-25 06:46:19', NULL),
(5, 'OD BHUBANESWAR RSM', 'RSM-OD-BBNSR', 'L3', 1, 1, '2026-07-25 09:46:08', NULL),
(6, 'BHUBANESWAR ASM', 'ASM-BBSNR', 'L2', 5, 1, '2026-07-25 09:46:52', NULL),
(7, 'EAST BHUBANESWAR', 'L1-EST-BBNSR', 'L1', 6, 1, '2026-07-25 09:51:09', NULL);

-- --------------------------------------------------------
-- Table structure for table `beats`
-- --------------------------------------------------------
DROP TABLE IF EXISTS `beats`;
CREATE TABLE `beats` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `code` varchar(100) NOT NULL,
  `description` varchar(500) DEFAULT NULL,
  `pincodes` varchar(500) DEFAULT NULL,
  `beat_type` enum('GT','MT','pharmacy','horeca','institutional','other') NOT NULL,
  `beat_grade` enum('rural','urban','semi_urban','metro','non_metro') DEFAULT NULL,
  `territory_id` int DEFAULT NULL,
  `erp_id` varchar(100) DEFAULT NULL,
  `is_active` tinyint(1) NOT NULL,
  `created_at` datetime DEFAULT (now()),
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_beats_code` (`code`),
  KEY `territory_id` (`territory_id`),
  KEY `ix_beats_id` (`id`),
  CONSTRAINT `beats_ibfk_1` FOREIGN KEY (`territory_id`) REFERENCES `geographies` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Dumping data for table `beats`
INSERT INTO `beats` (`id`, `name`, `code`, `description`, `pincodes`, `beat_type`, `beat_grade`, `territory_id`, `erp_id`, `is_active`, `created_at`) VALUES
(1, 'OMR ECR', 'OMR-ECR', NULL, NULL, 'other', NULL, 3, NULL, 1, '2026-07-25 07:13:46'),
(2, 'LAALPAHAD', 'LAALPAHAD', NULL, NULL, 'other', NULL, 5, NULL, 1, '2026-07-25 09:52:10');

-- --------------------------------------------------------
-- Table structure for table `outlets`
-- --------------------------------------------------------
DROP TABLE IF EXISTS `outlets`;
CREATE TABLE `outlets` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `code` varchar(100) DEFAULT NULL,
  `owner_name` varchar(255) DEFAULT NULL,
  `mobile` varchar(20) DEFAULT NULL,
  `address` text,
  `pincode` varchar(6) DEFAULT NULL,
  `gstin` varchar(15) DEFAULT NULL,
  `channel` enum('GT','MT','pharmacy','horeca','institutional','other') DEFAULT NULL,
  `shop_type` enum('kirana','medical','general','supermarket','hardware','other') DEFAULT NULL,
  `external_id` varchar(100) DEFAULT NULL,
  `beat_id` int DEFAULT NULL,
  `territory_id` int DEFAULT NULL,
  `gps_lat` float DEFAULT NULL,
  `gps_lng` float DEFAULT NULL,
  `erp_id` varchar(100) DEFAULT NULL,
  `status` varchar(50) DEFAULT 'active',
  `is_active` tinyint(1) NOT NULL,
  `created_at` datetime DEFAULT (now()),
  `updated_at` datetime DEFAULT (now()),
  `photo_url` text,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_outlets_mobile` (`mobile`),
  UNIQUE KEY `ix_outlets_code` (`code`),
  KEY `beat_id` (`beat_id`),
  KEY `territory_id` (`territory_id`),
  KEY `ix_outlets_id` (`id`),
  KEY `ix_outlets_external_id` (`external_id`),
  CONSTRAINT `outlets_ibfk_1` FOREIGN KEY (`beat_id`) REFERENCES `beats` (`id`),
  CONSTRAINT `outlets_ibfk_2` FOREIGN KEY (`territory_id`) REFERENCES `geographies` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --------------------------------------------------------
-- Table structure for table `outlet_versions`
-- --------------------------------------------------------
DROP TABLE IF EXISTS `outlet_versions`;
CREATE TABLE `outlet_versions` (
  `id` int NOT NULL AUTO_INCREMENT,
  `outlet_id` int NOT NULL,
  `version_number` int NOT NULL,
  `name` varchar(255) NOT NULL,
  `code` varchar(100) DEFAULT NULL,
  `owner_name` varchar(255) DEFAULT NULL,
  `mobile` varchar(20) DEFAULT NULL,
  `address` text,
  `pincode` varchar(6) DEFAULT NULL,
  `gstin` varchar(15) DEFAULT NULL,
  `channel` varchar(50) DEFAULT NULL,
  `shop_type` varchar(50) DEFAULT NULL,
  `beat_id` int DEFAULT NULL,
  `territory_id` int DEFAULT NULL,
  `gps_lat` float DEFAULT NULL,
  `gps_lng` float DEFAULT NULL,
  `status` varchar(50) DEFAULT NULL,
  `changed_by_id` int DEFAULT NULL,
  `change_summary` text,
  `created_at` datetime DEFAULT (now()),
  `photo_url` text,
  PRIMARY KEY (`id`),
  KEY `changed_by_id` (`changed_by_id`),
  KEY `ix_outlet_versions_outlet_id` (`outlet_id`),
  KEY `ix_outlet_versions_id` (`id`),
  CONSTRAINT `outlet_versions_ibfk_1` FOREIGN KEY (`outlet_id`) REFERENCES `outlets` (`id`) ON DELETE CASCADE,
  CONSTRAINT `outlet_versions_ibfk_2` FOREIGN KEY (`changed_by_id`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --------------------------------------------------------
-- Table structure for table `payments`
-- --------------------------------------------------------
DROP TABLE IF EXISTS `payments`;
CREATE TABLE `payments` (
  `id` int NOT NULL AUTO_INCREMENT,
  `payment_ref` varchar(50) NOT NULL,
  `order_id` int DEFAULT NULL,
  `outlet_id` int NOT NULL,
  `user_id` int NOT NULL,
  `amount` decimal(12,2) NOT NULL,
  `method` enum('cash','upi','cheque','neft') NOT NULL,
  `payment_type` enum('invoice_payment','advance','credit_note') NOT NULL,
  `transaction_ref` varchar(100) DEFAULT NULL,
  `status` enum('pending','collected','verified','rejected') NOT NULL,
  `denom_2000` int NOT NULL,
  `denom_500` int NOT NULL,
  `denom_200` int NOT NULL,
  `denom_100` int NOT NULL,
  `denom_50` int NOT NULL,
  `denom_20` int NOT NULL,
  `denom_10` int NOT NULL,
  `submission_id` int DEFAULT NULL,
  `collected_at` datetime DEFAULT (now()),
  `created_at` datetime DEFAULT (now()),
  `is_archived` tinyint(1) NOT NULL DEFAULT '0',
  `archived_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_payments_payment_ref` (`payment_ref`),
  KEY `order_id` (`order_id`),
  KEY `outlet_id` (`outlet_id`),
  KEY `user_id` (`user_id`),
  KEY `fk_payment_submission` (`submission_id`),
  CONSTRAINT `fk_payment_submission` FOREIGN KEY (`submission_id`) REFERENCES `payment_submissions` (`id`) ON DELETE SET NULL,
  CONSTRAINT `payments_ibfk_1` FOREIGN KEY (`order_id`) REFERENCES `orders` (`id`) ON DELETE SET NULL,
  CONSTRAINT `payments_ibfk_2` FOREIGN KEY (`outlet_id`) REFERENCES `outlets` (`id`) ON DELETE RESTRICT,
  CONSTRAINT `payments_ibfk_3` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT,
  CONSTRAINT `payments_ibfk_4` FOREIGN KEY (`submission_id`) REFERENCES `payment_submissions` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --------------------------------------------------------
-- Table structure for table `expenses`
-- --------------------------------------------------------
DROP TABLE IF EXISTS `expenses`;
CREATE TABLE `expenses` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `category` enum('travel','food','accommodation','communication','other') NOT NULL,
  `amount` decimal(10,2) NOT NULL,
  `description` text,
  `expense_date` date NOT NULL,
  `receipt_url` varchar(500) DEFAULT NULL,
  `status` enum('draft','submitted','approved','rejected') NOT NULL,
  `approved_by_id` int DEFAULT NULL,
  `approved_at` datetime DEFAULT NULL,
  `rejection_reason` text,
  `created_at` datetime DEFAULT (now()),
  `is_archived` tinyint(1) NOT NULL DEFAULT '0',
  `archived_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `approved_by_id` (`approved_by_id`),
  CONSTRAINT `expenses_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT,
  CONSTRAINT `expenses_ibfk_2` FOREIGN KEY (`approved_by_id`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --------------------------------------------------------
-- Table structure for table `attendance`
-- --------------------------------------------------------
DROP TABLE IF EXISTS `attendance`;
CREATE TABLE `attendance` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `date` date NOT NULL,
  `checkin_time` datetime DEFAULT NULL,
  `checkout_time` datetime DEFAULT NULL,
  `total_hours` float DEFAULT NULL,
  `timesheet_hours` float DEFAULT NULL,
  `activity_hours` float DEFAULT NULL,
  `attendance_type` enum('full_day','half_day','absent') DEFAULT NULL,
  `suggested_type` enum('full_day','half_day','absent') DEFAULT NULL,
  `approval_status` enum('pending','approved','rejected') NOT NULL,
  `approved_by_id` int DEFAULT NULL,
  `approved_at` datetime DEFAULT NULL,
  `rejection_reason` text,
  `notes` text,
  `created_at` datetime DEFAULT (now()),
  `updated_at` datetime DEFAULT (now()),
  `is_archived` tinyint(1) NOT NULL DEFAULT '0',
  `archived_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `approved_by_id` (`approved_by_id`),
  KEY `ix_attendance_date` (`date`),
  KEY `ix_attendance_user_id` (`user_id`),
  CONSTRAINT `attendance_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT,
  CONSTRAINT `attendance_ibfk_2` FOREIGN KEY (`approved_by_id`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --------------------------------------------------------
-- Table structure for table `timesheets`
-- --------------------------------------------------------
DROP TABLE IF EXISTS `timesheets`;
CREATE TABLE `timesheets` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `attendance_id` int DEFAULT NULL,
  `work_date` date NOT NULL,
  `checkin_time` datetime DEFAULT NULL,
  `checkout_time` datetime DEFAULT NULL,
  `checkin_lat` float DEFAULT NULL,
  `checkin_lng` float DEFAULT NULL,
  `checkout_lat` float DEFAULT NULL,
  `checkout_lng` float DEFAULT NULL,
  `checkin_address` varchar(300) DEFAULT NULL,
  `checkout_address` varchar(300) DEFAULT NULL,
  `status` enum('open','closed') NOT NULL,
  `approval_status` enum('pending','approved','rejected') NOT NULL,
  `approved_by_id` int DEFAULT NULL,
  `approved_at` datetime DEFAULT NULL,
  `rejection_reason` text,
  `activity_type` varchar(100) DEFAULT NULL,
  `notes` text,
  `created_at` datetime DEFAULT (now()),
  `is_archived` tinyint(1) NOT NULL DEFAULT '0',
  `archived_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `fk_timesheet_attendance` (`attendance_id`),
  KEY `fk_timesheet_approved_by` (`approved_by_id`),
  CONSTRAINT `fk_timesheet_approved_by` FOREIGN KEY (`approved_by_id`) REFERENCES `users` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_timesheet_attendance` FOREIGN KEY (`attendance_id`) REFERENCES `attendance` (`id`) ON DELETE SET NULL,
  CONSTRAINT `timesheets_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT,
  CONSTRAINT `timesheets_ibfk_2` FOREIGN KEY (`attendance_id`) REFERENCES `attendance` (`id`) ON DELETE SET NULL,
  CONSTRAINT `timesheets_ibfk_3` FOREIGN KEY (`approved_by_id`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --------------------------------------------------------
-- Table structure for table `visit_records`
-- --------------------------------------------------------
DROP TABLE IF EXISTS `visit_records`;
CREATE TABLE `visit_records` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `outlet_id` int NOT NULL,
  `timesheet_id` int DEFAULT NULL,
  `order_id` int DEFAULT NULL,
  `visit_time` datetime NOT NULL DEFAULT (now()),
  `checkout_time` datetime DEFAULT NULL,
  `gps_lat` float DEFAULT NULL,
  `gps_lng` float DEFAULT NULL,
  `distance_from_outlet` float DEFAULT NULL,
  `purpose` varchar(50) DEFAULT NULL,
  `visit_type` varchar(30) DEFAULT NULL,
  `notes` text,
  `is_joint_visit` tinyint(1) NOT NULL,
  `joint_with_user_id` int DEFAULT NULL,
  `joint_with_name` varchar(255) DEFAULT NULL,
  `joint_with_role` varchar(100) DEFAULT NULL,
  `joint_notes` text,
  `created_at` datetime DEFAULT (now()),
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `outlet_id` (`outlet_id`),
  KEY `timesheet_id` (`timesheet_id`),
  KEY `order_id` (`order_id`),
  KEY `joint_with_user_id` (`joint_with_user_id`),
  CONSTRAINT `visit_records_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT,
  CONSTRAINT `visit_records_ibfk_2` FOREIGN KEY (`outlet_id`) REFERENCES `outlets` (`id`) ON DELETE RESTRICT,
  CONSTRAINT `visit_records_ibfk_3` FOREIGN KEY (`timesheet_id`) REFERENCES `timesheets` (`id`) ON DELETE SET NULL,
  CONSTRAINT `visit_records_ibfk_4` FOREIGN KEY (`order_id`) REFERENCES `orders` (`id`) ON DELETE SET NULL,
  CONSTRAINT `visit_records_ibfk_5` FOREIGN KEY (`joint_with_user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --------------------------------------------------------
-- Table structure for table `material_requests`
-- --------------------------------------------------------
DROP TABLE IF EXISTS `material_requests`;
CREATE TABLE `material_requests` (
  `id` int NOT NULL AUTO_INCREMENT,
  `mr_number` varchar(30) NOT NULL,
  `user_id` int NOT NULL,
  `outlet_id` int NOT NULL,
  `company_profile_id` int DEFAULT NULL,
  `category` varchar(100) DEFAULT NULL,
  `description` text NOT NULL,
  `status` enum('draft','submitted','acknowledged','in_progress','completed','cancelled') NOT NULL,
  `sync_status` enum('not_applicable','pending','synced','failed') NOT NULL,
  `cmms_ref` varchar(100) DEFAULT NULL,
  `cmms_response` text,
  `sync_error` text,
  `sync_retries` int NOT NULL,
  `submitted_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT (now()),
  `updated_at` datetime DEFAULT (now()),
  `vendor_id` int DEFAULT NULL,
  `image_url` text,
  `is_archived` tinyint(1) NOT NULL DEFAULT '0',
  `archived_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_material_requests_mr_number` (`mr_number`),
  KEY `user_id` (`user_id`),
  KEY `outlet_id` (`outlet_id`),
  KEY `company_profile_id` (`company_profile_id`),
  CONSTRAINT `material_requests_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT,
  CONSTRAINT `material_requests_ibfk_2` FOREIGN KEY (`outlet_id`) REFERENCES `outlets` (`id`) ON DELETE RESTRICT,
  CONSTRAINT `material_requests_ibfk_3` FOREIGN KEY (`company_profile_id`) REFERENCES `company_profiles` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --------------------------------------------------------
-- Table structure for table `material_request_history_logs`
-- --------------------------------------------------------
DROP TABLE IF EXISTS `material_request_history_logs`;
CREATE TABLE `material_request_history_logs` (
  `id` int NOT NULL AUTO_INCREMENT,
  `material_request_id` int NOT NULL,
  `action` varchar(50) NOT NULL,
  `performed_by_id` int DEFAULT NULL,
  `old_status` varchar(50) DEFAULT NULL,
  `new_status` varchar(50) DEFAULT NULL,
  `vendor_id` int DEFAULT NULL,
  `notes` text,
  `created_at` datetime NOT NULL DEFAULT (now()),
  `is_archived` tinyint(1) NOT NULL DEFAULT '0',
  `archived_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `performed_by_id` (`performed_by_id`),
  KEY `vendor_id` (`vendor_id`),
  KEY `ix_material_request_history_logs_material_request_id` (`material_request_id`),
  KEY `ix_material_request_history_logs_id` (`id`),
  CONSTRAINT `material_request_history_logs_ibfk_1` FOREIGN KEY (`material_request_id`) REFERENCES `material_requests` (`id`) ON DELETE CASCADE,
  CONSTRAINT `material_request_history_logs_ibfk_2` FOREIGN KEY (`performed_by_id`) REFERENCES `users` (`id`) ON DELETE SET NULL,
  CONSTRAINT `material_request_history_logs_ibfk_3` FOREIGN KEY (`vendor_id`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --------------------------------------------------------
-- Table structure for table `vendor_quotations`
-- --------------------------------------------------------
DROP TABLE IF EXISTS `vendor_quotations`;
CREATE TABLE `vendor_quotations` (
  `id` int NOT NULL AUTO_INCREMENT,
  `material_request_id` int NOT NULL,
  `vendor_id` int NOT NULL,
  `quote_amount` decimal(10,2) NOT NULL,
  `lead_time_days` int DEFAULT NULL,
  `status` enum('pending','approved','rejected','held') NOT NULL,
  `notes` text,
  `created_at` datetime NOT NULL,
  `invoice_photo_url` text,
  `is_archived` tinyint(1) NOT NULL DEFAULT '0',
  `archived_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `material_request_id` (`material_request_id`),
  KEY `vendor_id` (`vendor_id`),
  KEY `ix_vendor_quotations_id` (`id`),
  CONSTRAINT `vendor_quotations_ibfk_1` FOREIGN KEY (`material_request_id`) REFERENCES `material_requests` (`id`) ON DELETE CASCADE,
  CONSTRAINT `vendor_quotations_ibfk_2` FOREIGN KEY (`vendor_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --------------------------------------------------------
-- Table structure for table `work_orders`
-- --------------------------------------------------------
DROP TABLE IF EXISTS `work_orders`;
CREATE TABLE `work_orders` (
  `id` int NOT NULL AUTO_INCREMENT,
  `quotation_id` int NOT NULL,
  `wo_number` varchar(100) NOT NULL,
  `status` enum('issued','concluded','cancelled') NOT NULL,
  `qc_status` enum('pending','passed','failed') NOT NULL,
  `notes` text,
  `created_at` datetime NOT NULL,
  `material_request_id` int DEFAULT NULL,
  `vendor_id` int DEFAULT NULL,
  `qc_photo_url` text,
  `qc_notes` text,
  `qc_verified_at` datetime DEFAULT NULL,
  `qc_verified_by_id` int DEFAULT NULL,
  `is_archived` tinyint(1) NOT NULL DEFAULT '0',
  `archived_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_work_orders_wo_number` (`wo_number`),
  KEY `quotation_id` (`quotation_id`),
  KEY `ix_work_orders_id` (`id`),
  CONSTRAINT `work_orders_ibfk_1` FOREIGN KEY (`quotation_id`) REFERENCES `vendor_quotations` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --------------------------------------------------------
-- Table structure for table `asset_capitalizations`
-- --------------------------------------------------------
DROP TABLE IF EXISTS `asset_capitalizations`;
CREATE TABLE `asset_capitalizations` (
  `id` int NOT NULL AUTO_INCREMENT,
  `ac_number` varchar(30) NOT NULL,
  `user_id` int NOT NULL,
  `outlet_id` int NOT NULL,
  `company_profile_id` int DEFAULT NULL,
  `item_name` varchar(255) NOT NULL,
  `item_code` varchar(100) DEFAULT NULL,
  `quantity` int NOT NULL,
  `warehouse_name` varchar(255) DEFAULT NULL,
  `deployed_by` enum('rep','vendor_technician') NOT NULL,
  `vendor_id` int DEFAULT NULL,
  `vendor_employee_id` int DEFAULT NULL,
  `status` enum('pending','deployed','failed') NOT NULL,
  `sync_status` enum('not_applicable','pending','synced','failed') NOT NULL,
  `cmms_ref` varchar(100) DEFAULT NULL,
  `sync_error` text,
  `sync_retries` int NOT NULL,
  `notes` text,
  `deployed_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT (now()),
  `updated_at` datetime DEFAULT (now()),
  `image_url` text,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_asset_capitalizations_ac_number` (`ac_number`),
  KEY `user_id` (`user_id`),
  KEY `outlet_id` (`outlet_id`),
  KEY `company_profile_id` (`company_profile_id`),
  KEY `vendor_id` (`vendor_id`),
  KEY `vendor_employee_id` (`vendor_employee_id`),
  CONSTRAINT `asset_capitalizations_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT,
  CONSTRAINT `asset_capitalizations_ibfk_2` FOREIGN KEY (`outlet_id`) REFERENCES `outlets` (`id`) ON DELETE RESTRICT,
  CONSTRAINT `asset_capitalizations_ibfk_3` FOREIGN KEY (`company_profile_id`) REFERENCES `company_profiles` (`id`) ON DELETE SET NULL,
  CONSTRAINT `asset_capitalizations_ibfk_4` FOREIGN KEY (`vendor_id`) REFERENCES `vendors` (`id`) ON DELETE SET NULL,
  CONSTRAINT `asset_capitalizations_ibfk_5` FOREIGN KEY (`vendor_employee_id`) REFERENCES `vendor_employees` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --------------------------------------------------------
-- Table structure for table `alerts`
-- --------------------------------------------------------
DROP TABLE IF EXISTS `alerts`;
CREATE TABLE `alerts` (
  `id` int NOT NULL AUTO_INCREMENT,
  `severity` enum('info','warning','critical') NOT NULL,
  `alert_type` enum('missing_checkin','stale_payment','stale_order','sync_failure','cmms_status_change','custom') NOT NULL,
  `title` varchar(200) NOT NULL,
  `message` text NOT NULL,
  `is_read` tinyint(1) NOT NULL,
  `created_at` datetime DEFAULT (now()),
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=14 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Dumping data for table `alerts`
INSERT INTO `alerts` (`id`, `severity`, `alert_type`, `title`, `message`, `is_read`, `created_at`) VALUES
(1, 'info', 'custom', 'Login OTP for Kalpana Muthu', 'OTP verification code for user \'kkalpanamuthu\' (kkalpanamuthu10@gmail.com): 313968 (Valid for 10 minutes)', 1, '2026-07-25 10:30:41'),
(2, 'info', 'custom', 'Login OTP for Kalpana Muthu', 'OTP verification code for user \'kkalpanamuthu\' (kkalpanamuthu10@gmail.com): 479292 (Valid for 10 minutes)', 0, '2026-07-25 11:26:00'),
(3, 'info', 'custom', 'Login OTP for Kalpana Muthu', 'OTP verification code for user \'kkalpanamuthu\' (kkalpanamuthu10@gmail.com): 595219 (Valid for 10 minutes)', 0, '2026-07-25 13:06:24'),
(4, 'info', 'custom', 'Login OTP for Kalpana Muthu', 'OTP verification code for user \'kkalpanamuthu\' (kkalpanamuthu10@gmail.com): 372963 (Valid for 10 minutes)', 0, '2026-07-25 13:34:56'),
(5, 'info', 'custom', 'Login OTP for Kalpana Muthu', 'OTP verification code for user \'kkalpanamuthu\' (kkalpanamuthu10@gmail.com): 955366 (Valid for 10 minutes)', 0, '2026-07-26 13:12:52'),
(6, 'info', 'custom', 'Login OTP for Kalpana Muthu', 'OTP verification code for user \'kkalpanamuthu\' (kkalpanamuthu10@gmail.com): 356757 (Valid for 10 minutes)', 0, '2026-07-26 13:19:25'),
(7, 'info', 'custom', 'Login OTP for Kalpana Muthu', 'OTP verification code for user \'kkalpanamuthu\' (kkalpanamuthu10@gmail.com): 854411 (Valid for 10 minutes)', 0, '2026-07-27 05:49:07'),
(8, 'info', 'custom', 'Login OTP for Kalpana Muthu', 'OTP verification code for user \'kkalpanamuthu\' (kkalpanamuthu10@gmail.com): 453446 (Valid for 10 minutes)', 0, '2026-07-27 08:07:15'),
(9, 'info', 'custom', 'Login OTP for Mohan Kuppiri', 'OTP verification code for user \'kuppri.mohan\' (kuppri.mohan@gmail.com): 377064 (Valid for 10 minutes)', 0, '2026-07-27 09:13:33'),
(10, 'info', 'custom', 'Login OTP for Arasu Tiruvallur', 'OTP verification code for user \'arasu.tiruvallur\' (arasu.tiruvallur@sravie.in): 707146 (Valid for 10 minutes)', 0, '2026-07-27 09:14:54'),
(11, 'info', 'custom', 'Login OTP for Kalpana Muthu', 'OTP verification code for user \'kkalpanamuthu\' (kkalpanamuthu10@gmail.com): 616898 (Valid for 10 minutes)', 0, '2026-07-27 09:23:39'),
(12, 'info', 'custom', 'Login OTP for Kalpana Muthu', 'OTP verification code for user \'kkalpanamuthu\' (kkalpanamuthu10@gmail.com): 906974 (Valid for 10 minutes)', 0, '2026-07-27 10:14:13'),
(13, 'info', 'custom', 'Login OTP for Vinod Kumar Kolli', 'OTP verification code for user \'vinodkumarkolli\' (vinodkumarkolli@gmail.com): 117996 (Valid for 10 minutes)', 0, '2026-07-27 10:45:19');

-- --------------------------------------------------------
-- Table structure for table `auto_flags`
-- --------------------------------------------------------
DROP TABLE IF EXISTS `auto_flags`;
CREATE TABLE `auto_flags` (
  `id` int NOT NULL AUTO_INCREMENT,
  `flag_type` enum('gps_out_of_range','short_visit','gps_spoofing','payment_mismatch','unusual_activity') NOT NULL,
  `severity` enum('low','medium','high','critical') NOT NULL,
  `status` enum('open','reviewed','dismissed','escalated') NOT NULL,
  `user_id` int NOT NULL,
  `entity_type` varchar(50) NOT NULL,
  `entity_id` int NOT NULL,
  `title` varchar(255) NOT NULL,
  `description` text,
  `metric_value` float DEFAULT NULL,
  `threshold_value` float DEFAULT NULL,
  `admin_rating` int DEFAULT NULL,
  `reviewed_by_id` int DEFAULT NULL,
  `reviewed_at` datetime DEFAULT NULL,
  `review_notes` text,
  `created_at` datetime DEFAULT (now()),
  PRIMARY KEY (`id`),
  KEY `reviewed_by_id` (`reviewed_by_id`),
  KEY `ix_auto_flags_user_id` (`user_id`),
  CONSTRAINT `auto_flags_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `auto_flags_ibfk_2` FOREIGN KEY (`reviewed_by_id`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --------------------------------------------------------
-- Table structure for table `local_channel_partners`
-- --------------------------------------------------------
DROP TABLE IF EXISTS `local_channel_partners`;
CREATE TABLE `local_channel_partners` (
  `id` int NOT NULL AUTO_INCREMENT,
  `code` varchar(50) NOT NULL,
  `name` varchar(255) NOT NULL,
  `territory_name` varchar(100) DEFAULT NULL,
  `service_category` varchar(100) DEFAULT NULL,
  `phone` varchar(20) DEFAULT NULL,
  `email` varchar(255) DEFAULT NULL,
  `is_active` tinyint(1) NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `beat_type` varchar(50) NOT NULL DEFAULT 'GT',
  `partner_type` varchar(100) DEFAULT 'Distributor',
  `sales_channels` text,
  `geography_id` int DEFAULT NULL,
  `contact_person` varchar(255) DEFAULT NULL,
  `mobile` varchar(20) DEFAULT NULL,
  `address` text,
  `erp_id` varchar(100) DEFAULT NULL,
  `notification_preference` varchar(50) NOT NULL DEFAULT 'none',
  `notification_channel` varchar(50) NOT NULL DEFAULT 'email',
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_local_channel_partners_code` (`code`),
  KEY `ix_local_channel_partners_id` (`id`),
  KEY `ix_local_channel_partners_territory_name` (`territory_name`),
  KEY `ix_local_channel_partners_service_category` (`service_category`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Dumping data for table `local_channel_partners`
INSERT INTO `local_channel_partners` (`id`, `code`, `name`, `territory_name`, `service_category`, `phone`, `email`, `is_active`, `created_at`, `updated_at`, `beat_type`, `partner_type`, `sales_channels`, `geography_id`, `contact_person`, `mobile`, `address`, `erp_id`, `notification_preference`, `notification_channel`) VALUES
(1, 'CP-81ED51', 'Mahaveer Agencies - Ramapuram', 'CHENNAI TN', NULL, NULL, NULL, 1, '2026-07-25 13:35:52', '2026-07-25 13:35:52', 'PHARMACY', 'Distributor', '["PHARMACY"]', 3, NULL, NULL, NULL, NULL, 'none', 'email'),
(2, 'CP-26B084', 'Siva Agencies - Kodungaiyur', 'CHENNAI TN', NULL, NULL, NULL, 1, '2026-07-25 13:36:31', '2026-07-25 13:36:31', 'PHARMACY', 'Distributor', '["PHARMACY"]', 3, NULL, NULL, NULL, NULL, 'none', 'email'),
(3, 'CP-0DED10', 'V.N.S Agencies', 'CHENNAI TN', NULL, NULL, NULL, 1, '2026-07-25 13:36:53', '2026-07-25 13:36:53', 'GT', 'Distributor', '["GT"]', 3, NULL, NULL, NULL, NULL, 'none', 'email'),
(4, 'CP-BB2FEA', 'Sample Odisha Distributor', 'BHUBANESWAR ODISHA', NULL, NULL, NULL, 1, '2026-07-26 13:12:44', '2026-07-26 13:12:44', 'OTHER', 'Distributor', '["OTHER"]', 5, NULL, NULL, NULL, NULL, 'none', 'email');

-- --------------------------------------------------------
-- Table structure for table `pincode_territory_mappings`
-- --------------------------------------------------------
DROP TABLE IF EXISTS `pincode_territory_mappings`;
CREATE TABLE `pincode_territory_mappings` (
  `id` int NOT NULL AUTO_INCREMENT,
  `pincode` varchar(10) NOT NULL,
  `territory_name` varchar(100) NOT NULL,
  `region_name` varchar(100) DEFAULT NULL,
  `state_name` varchar(100) DEFAULT NULL,
  `is_active` tinyint(1) NOT NULL,
  `created_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_pincode_territory_mappings_pincode` (`pincode`),
  KEY `ix_pincode_territory_mappings_id` (`id`),
  KEY `ix_pincode_territory_mappings_territory_name` (`territory_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --------------------------------------------------------
-- Table structure for table `user_otps`
-- --------------------------------------------------------
DROP TABLE IF EXISTS `user_otps`;
CREATE TABLE `user_otps` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `email` varchar(255) NOT NULL,
  `otp_code` varchar(6) NOT NULL,
  `expires_at` datetime NOT NULL,
  `is_used` tinyint(1) NOT NULL,
  `created_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_user_otps_email` (`email`),
  KEY `ix_user_otps_id` (`id`),
  KEY `ix_user_otps_user_id` (`user_id`),
  CONSTRAINT `user_otps_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=14 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Dumping data for table `user_otps`
INSERT INTO `user_otps` (`id`, `user_id`, `email`, `otp_code`, `expires_at`, `is_used`, `created_at`) VALUES
(1, 2, 'kkalpanamuthu10@gmail.com', '313968', '2026-07-25 10:40:42', 1, '2026-07-25 10:30:42'),
(2, 2, 'kkalpanamuthu10@gmail.com', '479292', '2026-07-25 11:36:00', 1, '2026-07-25 11:26:00'),
(3, 2, 'kkalpanamuthu10@gmail.com', '595219', '2026-07-25 13:16:25', 1, '2026-07-25 13:06:25'),
(4, 2, 'kkalpanamuthu10@gmail.com', '372963', '2026-07-25 13:44:56', 1, '2026-07-25 13:34:56'),
(5, 2, 'kkalpanamuthu10@gmail.com', '955366', '2026-07-26 13:22:53', 1, '2026-07-26 13:12:53'),
(6, 2, 'kkalpanamuthu10@gmail.com', '356757', '2026-07-26 13:29:26', 1, '2026-07-26 13:19:26'),
(7, 2, 'kkalpanamuthu10@gmail.com', '854411', '2026-07-27 05:59:08', 1, '2026-07-27 05:49:08'),
(8, 2, 'kkalpanamuthu10@gmail.com', '453446', '2026-07-27 08:17:16', 1, '2026-07-27 08:07:16'),
(9, 3, 'kuppri.mohan@gmail.com', '377064', '2026-07-27 09:23:33', 1, '2026-07-27 09:13:33'),
(10, 4, 'arasu.tiruvallur@sravie.in', '707146', '2026-07-27 09:24:55', 1, '2026-07-27 09:14:55'),
(11, 2, 'kkalpanamuthu10@gmail.com', '616898', '2026-07-27 09:33:40', 1, '2026-07-27 09:23:40'),
(12, 2, 'kkalpanamuthu10@gmail.com', '906974', '2026-07-27 10:24:14', 1, '2026-07-27 10:14:14'),
(13, 5, 'vinodkumarkolli@gmail.com', '117996', '2026-07-27 10:55:20', 1, '2026-07-27 10:45:20');

-- --------------------------------------------------------
-- Table structure for table `beat_channel_partners`
-- --------------------------------------------------------
DROP TABLE IF EXISTS `beat_channel_partners`;
CREATE TABLE `beat_channel_partners` (
  `id` int NOT NULL AUTO_INCREMENT,
  `beat_id` int NOT NULL,
  `channel_partner_id` int NOT NULL,
  `created_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_beat_channel_partners_channel_partner_id` (`channel_partner_id`),
  KEY `ix_beat_channel_partners_beat_id` (`beat_id`),
  KEY `ix_beat_channel_partners_id` (`id`),
  CONSTRAINT `beat_channel_partners_ibfk_1` FOREIGN KEY (`beat_id`) REFERENCES `beats` (`id`) ON DELETE CASCADE,
  CONSTRAINT `beat_channel_partners_ibfk_2` FOREIGN KEY (`channel_partner_id`) REFERENCES `local_channel_partners` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --------------------------------------------------------
-- Table structure for table `stock_movements`
-- --------------------------------------------------------
DROP TABLE IF EXISTS `stock_movements`;
CREATE TABLE `stock_movements` (
  `id` int NOT NULL AUTO_INCREMENT,
  `product_id` int NOT NULL,
  `movement_type` varchar(50) NOT NULL,
  `quantity` int NOT NULL,
  `reference_no` varchar(100) DEFAULT NULL,
  `notes` text,
  `created_by_id` int DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `warehouse_id` int DEFAULT NULL,
  `is_archived` tinyint(1) NOT NULL DEFAULT '0',
  `archived_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `created_by_id` (`created_by_id`),
  KEY `ix_stock_movements_product_id` (`product_id`),
  KEY `ix_stock_movements_id` (`id`),
  CONSTRAINT `stock_movements_ibfk_1` FOREIGN KEY (`product_id`) REFERENCES `products` (`id`) ON DELETE CASCADE,
  CONSTRAINT `stock_movements_ibfk_2` FOREIGN KEY (`created_by_id`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Dumping data for table `stock_movements`
INSERT INTO `stock_movements` (`id`, `product_id`, `movement_type`, `quantity`, `reference_no`, `notes`, `created_by_id`, `created_at`, `warehouse_id`, `is_archived`, `archived_at`) VALUES
(1, 3, 'INWARD', 50, 'SAMPLE-ITEMS-50', '', 2, '2026-07-26 12:26:27', 2, 0, NULL),
(2, 3, 'ADJUSTMENT', 45, NULL, 'Missing Stock', 2, '2026-07-26 12:27:00', 2, 0, NULL);

-- --------------------------------------------------------
-- Table structure for table `system_webhooks`
-- --------------------------------------------------------
DROP TABLE IF EXISTS `system_webhooks`;
CREATE TABLE `system_webhooks` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `event_type` enum('attendance_checkin','attendance_checkout','timesheet_submitted','timesheet_approved','order_created','order_status_updated','payment_recorded','expense_submitted','expense_approved','visit_checkin','outlet_created','material_request_created','material_request_approved','work_order_created','work_order_qc_passed','marketing_asset_created') NOT NULL,
  `endpoint_url` varchar(500) NOT NULL,
  `secret_key` varchar(255) DEFAULT NULL,
  `is_active` tinyint(1) NOT NULL,
  `last_triggered_at` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_system_webhooks_id` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --------------------------------------------------------
-- Table structure for table `beat_types_master`
-- --------------------------------------------------------
DROP TABLE IF EXISTS `beat_types_master`;
CREATE TABLE `beat_types_master` (
  `id` int NOT NULL AUTO_INCREMENT,
  `code` varchar(50) NOT NULL,
  `name` varchar(100) NOT NULL,
  `description` varchar(255) DEFAULT NULL,
  `is_active` tinyint(1) NOT NULL,
  `created_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_beat_types_master_code` (`code`),
  KEY `ix_beat_types_master_id` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Dumping data for table `beat_types_master`
INSERT INTO `beat_types_master` (`id`, `code`, `name`, `description`, `is_active`, `created_at`) VALUES
(1, 'GT', 'General Trade (GT)', 'Retail stores, kirana shops, and general trade outlets', 1, '2026-07-24 13:54:07'),
(2, 'MT', 'Modern Trade (MT)', 'Supermarkets, hypermarkets, and chain stores', 1, '2026-07-24 13:54:07'),
(3, 'PHARMACY', 'Pharmacy', 'Medical stores and pharmacies', 1, '2026-07-24 13:54:07'),
(4, 'HORECA', 'HORECA', 'Hotels, restaurants, cafes, and catering', 1, '2026-07-24 13:54:07'),
(5, 'INSTITUTIONAL', 'Institutional', 'Hospitals, corporate offices, and institutional buyers', 1, '2026-07-24 13:54:07'),
(6, 'OTHER', 'Other', 'Miscellaneous and specialized outlets', 1, '2026-07-24 13:54:07');

-- --------------------------------------------------------
-- Table structure for table `orders`
-- --------------------------------------------------------
DROP TABLE IF EXISTS `orders`;
CREATE TABLE `orders` (
  `id` int NOT NULL AUTO_INCREMENT,
  `order_number` varchar(30) NOT NULL,
  `outlet_id` int NOT NULL,
  `user_id` int NOT NULL,
  `beat_id` int DEFAULT NULL,
  `company_profile_id` int DEFAULT NULL,
  `status` enum('draft','submitted','confirmed','dispatched','delivered','cancelled') NOT NULL,
  `flow_type` enum('zap_invoice','connect') NOT NULL,
  `sync_status` enum('not_applicable','pending','synced','failed') NOT NULL,
  `payment_settlement` enum('unpaid','partial','paid') NOT NULL,
  `connect_ref` varchar(100) DEFAULT NULL,
  `order_date` date NOT NULL,
  `notes` text,
  `sync_error` text,
  `sync_retries` int NOT NULL,
  `created_at` datetime DEFAULT (now()),
  `updated_at` datetime DEFAULT (now()),
  `channel_partner_id` int DEFAULT NULL,
  `is_archived` tinyint(1) NOT NULL DEFAULT '0',
  `archived_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_orders_order_number` (`order_number`),
  KEY `outlet_id` (`outlet_id`),
  KEY `user_id` (`user_id`),
  KEY `beat_id` (`beat_id`),
  KEY `company_profile_id` (`company_profile_id`),
  CONSTRAINT `orders_ibfk_1` FOREIGN KEY (`outlet_id`) REFERENCES `outlets` (`id`) ON DELETE RESTRICT,
  CONSTRAINT `orders_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT,
  CONSTRAINT `orders_ibfk_3` FOREIGN KEY (`beat_id`) REFERENCES `beats` (`id`) ON DELETE SET NULL,
  CONSTRAINT `orders_ibfk_4` FOREIGN KEY (`company_profile_id`) REFERENCES `company_profiles` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --------------------------------------------------------
-- Table structure for table `order_items`
-- --------------------------------------------------------
DROP TABLE IF EXISTS `order_items`;
CREATE TABLE `order_items` (
  `id` int NOT NULL AUTO_INCREMENT,
  `order_id` int NOT NULL,
  `product_id` int NOT NULL,
  `quantity` int NOT NULL,
  `unit_price` decimal(10,2) NOT NULL,
  `gst_rate` decimal(5,2) NOT NULL,
  `discount_pct` decimal(5,2) NOT NULL,
  `is_archived` tinyint(1) NOT NULL DEFAULT '0',
  `archived_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `order_id` (`order_id`),
  KEY `product_id` (`product_id`),
  CONSTRAINT `order_items_ibfk_1` FOREIGN KEY (`order_id`) REFERENCES `orders` (`id`) ON DELETE CASCADE,
  CONSTRAINT `order_items_ibfk_2` FOREIGN KEY (`product_id`) REFERENCES `products` (`id`) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --------------------------------------------------------
-- Table structure for table `order_history_logs`
-- --------------------------------------------------------
DROP TABLE IF EXISTS `order_history_logs`;
CREATE TABLE `order_history_logs` (
  `id` int NOT NULL AUTO_INCREMENT,
  `order_id` int NOT NULL,
  `action` varchar(100) NOT NULL,
  `old_status` varchar(50) DEFAULT NULL,
  `new_status` varchar(50) DEFAULT NULL,
  `channel_partner_id` int DEFAULT NULL,
  `performed_by_id` int DEFAULT NULL,
  `notes` text,
  `created_at` datetime NOT NULL DEFAULT (now()),
  PRIMARY KEY (`id`),
  KEY `channel_partner_id` (`channel_partner_id`),
  KEY `performed_by_id` (`performed_by_id`),
  KEY `ix_order_history_logs_id` (`id`),
  KEY `ix_order_history_logs_order_id` (`order_id`),
  CONSTRAINT `order_history_logs_ibfk_1` FOREIGN KEY (`order_id`) REFERENCES `orders` (`id`) ON DELETE CASCADE,
  CONSTRAINT `order_history_logs_ibfk_2` FOREIGN KEY (`channel_partner_id`) REFERENCES `local_channel_partners` (`id`) ON DELETE SET NULL,
  CONSTRAINT `order_history_logs_ibfk_3` FOREIGN KEY (`performed_by_id`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

SET FOREIGN_KEY_CHECKS=1;
