-- DataGrip 접속: localhost:3307 / root / root / lecture05
-- 테이블: users, products, sales(월별 파티션), sales_flat(파티션 없음), orders(30만, 실습용)

-- 1. 둘러보기
SELECT * FROM sales LIMIT 20;
SELECT COUNT(*) FROM sales;
SELECT PARTITION_NAME, TABLE_ROWS FROM information_schema.PARTITIONS
 WHERE TABLE_SCHEMA='lecture05' AND TABLE_NAME='sales';      -- 월별 건수 분포

-- 2. 인덱스: 같은 조건, 인덱스 유무
EXPLAIN SELECT * FROM sales WHERE user_id = 777;             -- idx_user 사용
EXPLAIN SELECT * FROM sales WHERE amount = 5000;             -- 인덱스 없음 -> 전체 스캔
EXPLAIN SELECT * FROM sales WHERE status = 'CANCELED';       -- 값 종류 3개(카디널리티 낮음)
SELECT status, COUNT(*) FROM sales GROUP BY status;

-- 3. 파티셔닝: partitions 컬럼을 보자
EXPLAIN SELECT COUNT(*) FROM sales      WHERE created_at >= '2026-03-01' AND created_at < '2026-04-01';  -- p03 (+p01: MySQL 은 TO_DAYS 가 NULL 일 수 있어 첫 파티션을 같이 봄) 2개만
EXPLAIN SELECT COUNT(*) FROM sales_flat WHERE created_at >= '2026-03-01' AND created_at < '2026-04-01';  -- partitions 가 NULL = 파티션 없음, rows 50만 전체
EXPLAIN SELECT COUNT(*) FROM sales      WHERE user_id = 777;   -- 파티션 키가 조건에 없다 -> 12개 파티션 전부
EXPLAIN SELECT COUNT(*) FROM sales      WHERE DATE(created_at) = '2026-03-05';  -- 컬럼에 함수 -> 프루닝 안 됨(전체)
-- 오래된 데이터 지우기: 파티션 통째로 (DELETE 수십만 건과 비교)
-- ALTER TABLE sales DROP PARTITION p01;

-- 4. OLAP 성격 쿼리 (전체를 훑고 집계)
SELECT DATE_FORMAT(created_at,'%Y-%m') ym, COUNT(*) cnt, SUM(amount) total
  FROM sales WHERE status <> 'CANCELED' GROUP BY ym ORDER BY ym;

SELECT p.category, SUM(s.amount) total, COUNT(*) cnt
  FROM sales s JOIN products p ON p.id = s.product_id
 WHERE s.status <> 'CANCELED' GROUP BY p.category ORDER BY total DESC;

SELECT u.city, COUNT(*) cnt, SUM(s.amount) total
  FROM sales s JOIN users u ON u.id = s.user_id
 GROUP BY u.city ORDER BY total DESC;

-- 5. OLTP 성격 쿼리 (한 사용자, 몇 건)
SELECT s.*, p.name FROM sales s JOIN products p ON p.id = s.product_id
 WHERE s.user_id = 777 ORDER BY s.created_at DESC LIMIT 10;
