"use client";

import { type ReactNode, useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  CircleHelp,
  Copy,
  Globe,
  Headphones,
  History,
  MessageCircleMore,
  Monitor,
  Settings2,
  Shield,
  Sparkles,
  UserRound,
  WalletCards,
  Zap,
} from "lucide-react";

type TabKey = "store" | "setup" | "profile" | "support";
type DeviceKey = "ios" | "android" | "desktop";

type BootstrapResponse = {
  user: {
    telegram_id: number;
    username: string | null;
    balance_ton: number;
    referrals_count: number;
    ref_link: string;
  };
  status: {
    vpn_active: boolean;
    dns_active: boolean;
    active_until: string | null;
    state: "online" | "offline";
  };
  prices: {
    rate_rub_per_ton: number;
    plans: Array<{
      code: "vpn" | "dns" | "pro";
      title: string;
      subtitle: string;
      price_rub: number;
      price_ton: number;
    }>;
  };
  links: {
    bot: string;
    p2p: string;
    support: string;
  };
  install: {
    vpn_keys: Array<{ key_id: number; access_url: string; expires_at: string }>;
    dns: Array<{ access_id: number; dns_server_ip: string; current_ip: string | null; expires_at: string }>;
  };
};

type FaqResponse = { items: Array<{ q: string; a: string }> };
type PaymentResponse = {
  payment_code: string;
  amount_ton: number;
  amount_rub: number;
  expires_at: string;
  ton_link: string;
  bot_check_link: string;
};

type TelegramWebApp = {
  ready: () => void;
  expand: () => void;
  openLink?: (url: string) => void;
  initDataUnsafe?: { user?: { id?: number } };
};

const API_BASE =
  process.env.NEXT_PUBLIC_MINI_API_BASE ||
  (typeof window !== "undefined" ? window.location.origin : "http://localhost:8080");

export default function Home() {
  const [tab, setTab] = useState<TabKey>("store");
  const [device, setDevice] = useState<DeviceKey>("ios");
  const [tgId, setTgId] = useState<number>(2096689952);
  const [bootstrap, setBootstrap] = useState<BootstrapResponse | null>(null);
  const [faq, setFaq] = useState<FaqResponse["items"]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [paymentInfo, setPaymentInfo] = useState<PaymentResponse | null>(null);
  const [paymentBusy, setPaymentBusy] = useState(false);

  const webApp = useMemo(
    () =>
      typeof window === "undefined"
        ? undefined
        : (window as Window & { Telegram?: { WebApp?: TelegramWebApp } }).Telegram?.WebApp,
    []
  );

  useEffect(() => {
    webApp?.ready();
    webApp?.expand();
    const id = webApp?.initDataUnsafe?.user?.id;
    if (id) setTgId(id);
  }, [webApp]);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const [bootstrapRes, faqRes] = await Promise.all([
          fetch(`${API_BASE}/api/mini/bootstrap?tg_id=${tgId}`),
          fetch(`${API_BASE}/api/mini/faq`),
        ]);
        if (!bootstrapRes.ok) throw new Error("bootstrap_failed");
        if (!faqRes.ok) throw new Error("faq_failed");

        const bootstrapJson = (await bootstrapRes.json()) as BootstrapResponse;
        const faqJson = (await faqRes.json()) as FaqResponse;
        setBootstrap(bootstrapJson);
        setFaq(faqJson.items || []);
      } catch {
        setError("Не удалось загрузить данные. Проверьте API.");
      } finally {
        setLoading(false);
      }
    };

    void load();
  }, [tgId]);

  const openLink = (url: string) => {
    if (webApp?.openLink) {
      webApp.openLink(url);
      return;
    }
    window.open(url, "_blank");
  };

  const createPayment = async (product: "vpn" | "dns" | "pro") => {
    setPaymentBusy(true);
    try {
      const response = await fetch(`${API_BASE}/api/mini/create-payment`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tg_id: tgId, product }),
      });
      if (!response.ok) throw new Error("payment_failed");
      const data = (await response.json()) as PaymentResponse;
      setPaymentInfo(data);
      openLink(data.ton_link);
    } catch {
      setError("Ошибка создания платежа. Попробуйте снова.");
    } finally {
      setPaymentBusy(false);
    }
  };

  const copyText = async (value: string) => {
    try {
      await navigator.clipboard.writeText(value);
    } catch {
      setError("Не удалось скопировать в буфер обмена.");
    }
  };

  const activeVpnKey = bootstrap?.install.vpn_keys?.[0];
  const activeDns = bootstrap?.install.dns?.[0];

  return (
    <main className="min-h-screen px-3 py-4 sm:px-6 sm:py-6">
      <section className="phone-shell mx-auto min-h-[92vh] w-full max-w-md p-5 pb-28 sm:min-h-[820px]">
        <header className="relative z-10 mb-6 flex items-center justify-between">
          <button className="secondary inline-flex h-10 w-10 items-center justify-center">
            {tab === "store" ? <Sparkles size={18} /> : <ArrowLeft size={18} />}
          </button>
          <div className="text-center">
            <p className="accent-font text-[31px] font-semibold leading-[1] tracking-tight">DNS.VPN</p>
            <p className="text-xs text-[var(--muted)]">мини-приложение</p>
          </div>
          <button className="secondary inline-flex h-10 w-10 items-center justify-center">
            <MessageCircleMore size={18} />
          </button>
        </header>

        <div className="relative z-10 space-y-4">
          {loading && <article className="glass p-4 text-sm text-[var(--muted)]">Загружаю данные...</article>}
          {error && !loading && <article className="rounded-2xl border border-[var(--danger)]/30 bg-red-500/10 p-4 text-sm">{error}</article>}

          {bootstrap && tab === "store" && (
            <div className="space-y-4">
              <article className="glass reveal px-5 py-5">
                <div className="mb-6 flex h-44 items-center justify-center">
                  <div className="relative flex h-30 w-30 items-center justify-center rounded-full border border-white/10">
                    <div className="absolute h-50 w-50 rounded-full border border-white/6" />
                    <div className="absolute h-70 w-70 rounded-full border border-white/6" />
                    <Shield className="text-white/90" size={66} />
                  </div>
                </div>

                <div className="mb-3 flex items-center justify-between">
                  <div>
                    <p className="text-3xl font-semibold leading-none">
                      {bootstrap.status.active_until ? `до ${bootstrap.status.active_until}` : "нет подписки"}
                    </p>
                    <p className="mt-1 text-sm text-[var(--muted)]">{bootstrap.status.state}</p>
                  </div>
                  <span className="secondary px-4 py-2 text-sm">курс {bootstrap.prices.rate_rub_per_ton} ₽/TON</span>
                </div>

                <button
                  disabled={paymentBusy}
                  onClick={() => createPayment("pro")}
                  className="cta mt-2 flex w-full items-center justify-between px-5 py-4 text-xl font-bold disabled:opacity-60"
                >
                  <span className="flex items-center gap-2">
                    <Globe size={22} />
                    Купить подписку
                  </span>
                  <span>от {Math.min(...bootstrap.prices.plans.map((p) => p.price_rub))} ₽</span>
                </button>
                <button onClick={() => openLink(bootstrap.links.p2p)} className="secondary mt-3 flex w-full items-center justify-center gap-2 px-5 py-3 text-lg">
                  <Zap size={20} />
                  Купить TON (P2P)
                </button>
              </article>

              {paymentInfo && (
                <article className="glass reveal p-4">
                  <p className="mb-2 text-sm">
                    Платеж <b>{paymentInfo.payment_code}</b> создан: {paymentInfo.amount_ton} TON (~{paymentInfo.amount_rub} ₽)
                  </p>
                  <div className="flex gap-2">
                    <button onClick={() => openLink(paymentInfo.ton_link)} className="cta w-full px-3 py-2 text-sm font-semibold">
                      Открыть оплату
                    </button>
                    <button onClick={() => openLink(paymentInfo.bot_check_link)} className="secondary w-full px-3 py-2 text-sm">
                      Я оплатил
                    </button>
                  </div>
                </article>
              )}

              <article className="glass reveal p-4">
                <h3 className="mb-3 text-lg font-semibold">Наши продукты</h3>
                <div className="space-y-3">
                  {bootstrap.prices.plans.map((plan) => (
                    <div key={plan.code} className="rounded-2xl border border-white/10 bg-black/15 p-3">
                      <div className="mb-1 flex items-center justify-between">
                        <p className="text-base font-semibold">{plan.title}</p>
                        <button onClick={() => createPayment(plan.code)} className="secondary px-2 py-1 text-xs">
                          Купить
                        </button>
                      </div>
                      <p className="text-sm text-[var(--muted)]">{plan.subtitle}</p>
                      <p className="mt-2 text-sm">
                        <span className="font-semibold">{plan.price_rub} ₽</span> · {plan.price_ton} TON
                      </p>
                    </div>
                  ))}
                </div>
              </article>
            </div>
          )}

          {bootstrap && tab === "setup" && (
            <div className="space-y-4">
              <article className="glass reveal p-5">
                <h2 className="mb-1 text-5xl font-semibold">Настройка</h2>
                <p className="text-sm text-[var(--muted)]">Подключение за 2 минуты. Deep link открывает установку прямо на устройстве.</p>
                <div className="mt-5 flex gap-2">
                  <button onClick={() => setDevice("ios")} className={`secondary px-3 py-2 text-sm ${device === "ios" ? "border-[var(--brand)] text-[var(--brand)]" : ""}`}>iOS</button>
                  <button onClick={() => setDevice("android")} className={`secondary px-3 py-2 text-sm ${device === "android" ? "border-[var(--brand)] text-[var(--brand)]" : ""}`}>Android</button>
                  <button onClick={() => setDevice("desktop")} className={`secondary px-3 py-2 text-sm ${device === "desktop" ? "border-[var(--brand)] text-[var(--brand)]" : ""}`}>Desktop</button>
                </div>
              </article>

              <article className="glass reveal p-4">
                <div className="space-y-3">
                  <div className="rounded-2xl border border-white/10 bg-black/15 p-3 text-sm">
                    <p className="font-semibold">VPN ключ</p>
                    <p className="text-[var(--muted)]">{activeVpnKey ? `Активен до ${activeVpnKey.expires_at}` : "Активного VPN ключа пока нет"}</p>
                  </div>
                  <div className="rounded-2xl border border-white/10 bg-black/15 p-3 text-sm">
                    <p className="font-semibold">DNS сервер</p>
                    <p className="text-[var(--muted)]">{activeDns?.dns_server_ip || "Будет доступен после покупки DNS"}</p>
                  </div>
                </div>
                <button
                  onClick={() => (activeVpnKey ? openLink(activeVpnKey.access_url) : openLink(bootstrap.links.bot))}
                  className="cta mt-4 w-full px-5 py-3 text-lg font-semibold"
                >
                  {activeVpnKey ? "Начать настройку на этом устройстве" : "Открыть бот и получить ключ"}
                </button>
                <button onClick={() => openLink(bootstrap.links.bot)} className="secondary mt-3 w-full px-5 py-3 text-lg">
                  Установить на другом устройстве
                </button>
              </article>
            </div>
          )}

          {bootstrap && tab === "profile" && (
            <div className="space-y-4">
              <article className="glass reveal p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="flex h-12 w-12 items-center justify-center rounded-full bg-gradient-to-br from-orange-400 to-pink-500 text-lg font-bold">
                      {(bootstrap.user.username?.[0] || "U").toUpperCase()}
                    </div>
                    <div>
                      <p className="text-xl font-semibold">{bootstrap.user.username || "Пользователь"}</p>
                      <p className="text-sm text-[var(--muted)]">id: {bootstrap.user.telegram_id}</p>
                    </div>
                  </div>
                  <button onClick={() => copyText(bootstrap.user.ref_link)} className="secondary inline-flex h-10 w-10 items-center justify-center">
                    <Copy size={18} />
                  </button>
                </div>
              </article>

              <article className="glass reveal p-4">
                <h3 className="mb-3 text-2xl font-semibold">Оплата</h3>
                <div className="space-y-3 text-sm">
                  <MenuLine icon={<WalletCards size={18} />} title="Способы оплаты" subtitle="TON / карта / SBP" />
                  <MenuLine icon={<History size={18} />} title="История операций" subtitle={`Баланс: ${bootstrap.user.balance_ton} TON`} />
                  <MenuLine icon={<Sparkles size={18} />} title="Реферальная программа" subtitle={`Приглашено: ${bootstrap.user.referrals_count}`} />
                </div>
              </article>

              <article className="glass reveal p-4">
                <h3 className="mb-3 text-2xl font-semibold">Ваша ссылка</h3>
                <div className="flex items-center justify-between rounded-2xl border border-white/12 bg-white/95 px-3 py-3 text-black">
                  <span className="truncate text-base">{bootstrap.user.ref_link}</span>
                  <button onClick={() => copyText(bootstrap.user.ref_link)}>
                    <Copy size={18} />
                  </button>
                </div>
              </article>
            </div>
          )}

          {bootstrap && tab === "support" && (
            <div className="space-y-4">
              <article className="glass reveal p-5">
                <Headphones size={34} className="mb-4 text-[var(--brand)]" />
                <h2 className="mb-2 text-4xl font-semibold">Поддержка</h2>
                <p className="text-sm text-[var(--muted)]">FAQ из API и моментальный переход в чат поддержки.</p>
              </article>

              <article className="glass reveal p-4">
                <div className="space-y-3 text-sm">
                  {faq.map((item) => (
                    <MenuLine key={item.q} icon={<CircleHelp size={18} />} title={item.q} subtitle={item.a} />
                  ))}
                  <button onClick={() => openLink(bootstrap.links.support)} className="cta w-full px-4 py-3 text-sm font-semibold">
                    Связаться с поддержкой
                  </button>
                </div>
              </article>
            </div>
          )}
        </div>

        <nav className="glass absolute inset-x-4 bottom-4 z-20 flex items-center justify-around p-2">
          <TabButton icon={<Shield size={20} />} label="Витрина" active={tab === "store"} onClick={() => setTab("store")} />
          <TabButton icon={<Settings2 size={20} />} label="Настройка" active={tab === "setup"} onClick={() => setTab("setup")} />
          <TabButton icon={<UserRound size={20} />} label="Профиль" active={tab === "profile"} onClick={() => setTab("profile")} />
          <TabButton icon={<Monitor size={20} />} label="Поддержка" active={tab === "support"} onClick={() => setTab("support")} />
        </nav>
      </section>
    </main>
  );
}

function TabButton({
  icon,
  label,
  active,
  onClick,
}: {
  icon: ReactNode;
  label: string;
  active?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex w-[23%] flex-col items-center gap-1 rounded-2xl px-2 py-2 text-[11px] transition ${
        active ? "bg-[var(--brand)] text-[#032119]" : "text-[var(--muted)] hover:bg-white/5"
      }`}
    >
      {icon}
      <span>{label}</span>
    </button>
  );
}

function MenuLine({
  icon,
  title,
  subtitle,
}: {
  icon: ReactNode;
  title: string;
  subtitle: string;
}) {
  return (
    <div className="flex w-full items-start gap-3 rounded-2xl border border-white/10 bg-black/15 p-3 text-left">
      <span className="secondary inline-flex h-9 w-9 items-center justify-center">{icon}</span>
      <span>
        <span className="block text-base font-semibold">{title}</span>
        <span className="block text-sm text-[var(--muted)]">{subtitle}</span>
      </span>
    </div>
  );
}
