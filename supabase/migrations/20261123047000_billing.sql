-- Corrective migration: billing abstraction (provider-neutral).
-- The provider (e.g. Stripe) is optional. Rows are written by the server only.

create table public.billing_subscriptions (
  organization_id uuid primary key references public.organizations(id) on delete cascade,
  plan_id text not null references public.plans(id),
  provider text not null default 'none',
  provider_customer_id text,
  provider_subscription_id text,
  status text not null default 'inactive'
    check (status in ('inactive', 'trialing', 'active', 'past_due', 'canceled')),
  current_period_start timestamptz,
  current_period_end timestamptz,
  cancel_at_period_end boolean not null default false,
  updated_at timestamptz not null default timezone('utc', now())
);

create table public.billing_invoices (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  provider text not null,
  provider_invoice_id text,
  amount_cents bigint not null default 0 check (amount_cents >= 0),
  currency text not null default 'usd',
  status text not null default 'draft'
    check (status in ('draft', 'open', 'paid', 'void', 'uncollectible')),
  hosted_url text,
  created_at timestamptz not null default timezone('utc', now()),
  unique (organization_id, provider, provider_invoice_id)
);

create index billing_invoices_org_created_idx
  on public.billing_invoices (organization_id, created_at desc);

alter table public.billing_subscriptions enable row level security;
alter table public.billing_invoices enable row level security;

create policy billing_subscriptions_select_member on public.billing_subscriptions
  for select to authenticated using (public.is_org_member(organization_id));
create policy billing_invoices_select_member on public.billing_invoices
  for select to authenticated using (public.is_org_member(organization_id));

-- Subscription and invoice rows are server-owned; no client write policies.
