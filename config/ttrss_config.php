<?php
       // *******************************************
       // *** Database configuration (important!) ***
       // *******************************************

       define('DB_TYPE', 'pgsql');
       define('DB_HOST', getenv('TTRSS_DB_HOST') ?: 'db');
       define('DB_USER', getenv('TTRSS_DB_USER') ?: 'ttrss');
       define('DB_NAME', getenv('TTRSS_DB_NAME') ?: 'ttrss');
       define('DB_PASS', getenv('TTRSS_DB_PASS') ?: 'password');
       define('DB_PORT', getenv('TTRSS_DB_PORT') ?: '5432');

       define('MYSQL_CHARSET', 'UTF8MB4');

       // ***********************************
       // *** Basic settings (important!) ***
       // ***********************************

       define('SELF_URL_PATH', getenv('TTRSS_SELF_URL_PATH') ?: 'http://localhost:18100/');
       define('SINGLE_USER_MODE', false);
       define('SIMPLE_UPDATE_MODE', false);

       // **********************
       // *** Files and dirs ***
       // **********************

       define('PHP_EXECUTABLE', '/usr/local/bin/php');
       define('LOCK_DIRECTORY', 'lock');
       define('CACHE_DIR', 'cache');
       define('ICONS_DIR', 'feed-icons');
       define('ICONS_URL', 'feed-icons');

       // *****************************
       // *** All other settings ***
       // *****************************

       define('CHECK_FOR_UPDATES', true);
       define('SESSION_COOKIE_LIFETIME', 86400);
       define('LOG_DESTINATION', 'sql');
