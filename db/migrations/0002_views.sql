create or replace view v_monthly_spend as
select
  date_trunc('month', t.posted_at)::date as month,
  coalesce(c.code, 'UNCATEGORIZED') as category,
  sum(case when s.amount is not null then s.amount else t.amount end) * -1 as spend
from transactions t
left join tx_splits s on s.transaction_id = t.id
left join categories c on c.id = s.category_id
where (s.amount is not null and s.amount < 0) or (s.amount is null and t.amount < 0)
group by 1,2;

create or replace view v_budget_status as
select
  b.category_id,
  c.code as category,
  b.period_start, b.period_end,
  b.amount as budget,
  coalesce(sum(case when s.amount < 0 then s.amount else 0 end) * -1, 0) as actual_spend,
  b.amount - (coalesce(sum(case when s.amount < 0 then s.amount else 0 end) * -1, 0)) as remaining
from budgets b
left join categories c on c.id = b.category_id
left join tx_splits s on s.category_id = b.category_id
left join transactions t on t.id = s.transaction_id
  and t.posted_at between b.period_start and b.period_end
group by 1,2,3,4,5;
