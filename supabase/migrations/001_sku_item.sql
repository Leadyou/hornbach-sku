-- Uruchom w Supabase: SQL Editor → New query → Run
-- Tabela katalogu SKU dla aplikacji dostępności

create table if not exists public.sku_item (
    sku text primary key,
    name text not null default '',
    stock_quantity integer not null default 0,
    lead_time_days integer not null default 0,
    available_from date null,
    delivery_location_code text not null default ''
);

alter table public.sku_item enable row level security;

-- Backend używa SERVICE_ROLE_KEY (omija RLS). Dla samej tabeli wystarczy brak polityk dla anon,
-- albo polityki pod publiczny dostęp — tu: tylko service role (bez polityk publicznych).

comment on table public.sku_item is 'Katalog SKU / stany / terminy — używane przez aplikację Hornbach SKU';
