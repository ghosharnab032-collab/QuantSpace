CREATE TABLE `corporate_actions` (
	`id` integer PRIMARY KEY AUTOINCREMENT,
	`ticker` text NOT NULL,
	`ex_date` text NOT NULL,
	`action_type` text NOT NULL,
	`ratio` text,
	`value` text,
	`description` text,
	`source` text NOT NULL,
	`recorded_at` text NOT NULL,
	CONSTRAINT `fk_corporate_actions_ticker_assets_ticker_fk` FOREIGN KEY (`ticker`) REFERENCES `assets`(`ticker`)
);
CREATE TABLE `assets` (
	`ticker` text PRIMARY KEY,
	`name` text NOT NULL,
	`exchange` text NOT NULL,
	`instrument_type` text NOT NULL,
	`isin` text,
	`sector` text,
	`industry` text,
	`face_value` text,
	`first_listed` text,
	`last_traded` text,
	`benchmark_index` text,
	`tax_type` text,
	CONSTRAINT "assets_check_1" CHECK(exchange IN ('NSE', 'BSE')),
	CONSTRAINT "assets_check_2" CHECK(length(trim(ticker)) > 0),
	CONSTRAINT "assets_check_3" CHECK(length(trim(name)) > 0)
);
CREATE TABLE `price_daily` (
	`id` integer PRIMARY KEY AUTOINCREMENT,
	`ticker` text NOT NULL,
	`trade_date` text NOT NULL,
	`open` text NOT NULL,
	`high` text NOT NULL,
	`low` text NOT NULL,
	`close` text NOT NULL,
	`volume` integer,
	`source` text NOT NULL,
	`source_file` text,
	`ingested_at` text NOT NULL,
	CONSTRAINT `fk_price_daily_ticker_assets_ticker_fk` FOREIGN KEY (`ticker`) REFERENCES `assets`(`ticker`),
	CONSTRAINT "price_daily_check_4" CHECK(CAST(open AS REAL) > 0),
	CONSTRAINT "price_daily_check_5" CHECK(CAST(high AS REAL) > 0),
	CONSTRAINT "price_daily_check_6" CHECK(CAST(low AS REAL) > 0),
	CONSTRAINT "price_daily_check_7" CHECK(CAST(close AS REAL) > 0),
	CONSTRAINT "price_daily_check_8" CHECK(volume IS NULL OR volume >= 0),
	CONSTRAINT "price_daily_check_9" CHECK(CAST(high AS REAL) >= CAST(open AS REAL)),
	CONSTRAINT "price_daily_check_10" CHECK(CAST(high AS REAL) >= CAST(close AS REAL)),
	CONSTRAINT "price_daily_check_11" CHECK(CAST(low AS REAL) <= CAST(open AS REAL)),
	CONSTRAINT "price_daily_check_12" CHECK(CAST(low AS REAL) <= CAST(close AS REAL))
);
CREATE TABLE `data_runs` (
	`run_id` text PRIMARY KEY,
	`started_at` text NOT NULL,
	`completed_at` text,
	`source` text NOT NULL,
	`tickers_processed` integer DEFAULT 0 NOT NULL,
	`rows_inserted` integer DEFAULT 0 NOT NULL,
	`rows_rejected` integer DEFAULT 0 NOT NULL,
	`rows_warned` integer DEFAULT 0 NOT NULL,
	`error_message` text,
	CONSTRAINT "data_runs_check_13" CHECK(length(trim(run_id)) > 0),
	CONSTRAINT "data_runs_check_14" CHECK(completed_at IS NULL OR completed_at >= started_at)
);
CREATE TABLE `rejected_rows` (
	`id` integer PRIMARY KEY AUTOINCREMENT,
	`run_id` text NOT NULL,
	`ticker` text,
	`trade_date` text,
	`source` text NOT NULL,
	`reason` text NOT NULL,
	`raw_payload` text NOT NULL,
	`rejected_at` text NOT NULL,
	CONSTRAINT `fk_rejected_rows_run_id_data_runs_run_id_fk` FOREIGN KEY (`run_id`) REFERENCES `data_runs`(`run_id`),
	CONSTRAINT "rejected_rows_check_15" CHECK(length(trim(reason)) > 0)
);
CREATE TABLE `dividend_yields` (
	`ticker` text NOT NULL,
	`effective_date` text NOT NULL,
	`dividend_yield` real NOT NULL,
	`source` text DEFAULT 'manual' NOT NULL,
	`recorded_at` text DEFAULT '' NOT NULL,
	CONSTRAINT `dividend_yields_pk` PRIMARY KEY(`ticker`, `effective_date`)
);
CREATE INDEX `idx_corporate_actions_ticker_date` ON `corporate_actions` (`ticker`,`ex_date`);
CREATE INDEX `idx_dividend_yields_ticker_date` ON `dividend_yields` (`ticker`,`effective_date`);
CREATE UNIQUE INDEX idx_price_daily_unique
ON price_daily(ticker, trade_date, source);