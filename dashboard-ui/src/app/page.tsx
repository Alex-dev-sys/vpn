"use client";

import { type ReactNode, useEffect, useMemo, useState } from "react";
import {
  BadgeHelp,
  CircleUserRound,
  Copy,
  ExternalLink,
  Headset,
  House,
  Link2,
  LoaderCircle,
  ShieldCheck,
  Settings,
  Sparkles,
  Zap,
} from "lucide-react";

type TabKey = "store" | "setup" | "profile" | "support";

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
type AuthFallback = {
  title: string;
  description: string;
  bot_link: string;
};
type PaymentResponse = {
  payment_code: string;
  amount_ton: number;
  amount_rub: number;
  expires_at: string;
  ton_link: string;
  bot_check_link: string;
};
type PaymentStage = "created" | "paid" | "confirmed" | "key_issued" | "expired";
type PaymentStatusResponse = {
  payment_code: string;
  status: string;
  stage: PaymentStage;
  is_final: boolean;
  expires_at: string;
};

type TelegramWebApp = {
  ready: () => void;
  expand: () => void;
  openLink?: (url: string) => void;
  initData?: string;
  initDataUnsafe?: { user?: { id?: number } };
};

const API_BASE =
  process.env.NEXT_PUBLIC_MINI_API_BASE ||
  (typeof window !== "undefined" ? window.location.origin : "http://localhost:8080");

export default function Home() {
  const [tab, setTab] = useState<TabKey>("store");
  const [tgId, setTgId] = useState<number>(2096689952);
  const [initData, setInitData] = useState<string>("");
  const [bootstrap, setBootstrap] = useState<BootstrapResponse | null>(null);
  const [faq, setFaq] = useState<FaqResponse["items"]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [payment, setPayment] = useState<PaymentResponse | null>(null);
  const [paymentStage, setPaymentStage] = useState<PaymentStage>("created");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [authFallback, setAuthFallback] = useState<AuthFallback | null>(null);

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
    if (webApp?.initData) setInitData(webApp.initData);
  }, [webApp]);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError(null);
      setAuthFallback(null);
      let authFailed = false;
      try {
        const [bootstrapRes, faqRes] = await Promise.all([
          fetch(
            `${API_BASE}/api/mini/bootstrap?tg_id=${tgId}${
              initData ? `&init_data=${encodeURIComponent(initData)}` : ""
            }`
          ),
          fetch(`${API_BASE}/api/mini/faq`),
        ]);

        if (!bootstrapRes.ok) {
          const bootstrapError = await bootstrapRes.json().catch(() => null);
          if (bootstrapError?.fallback) {
            setAuthFallback(bootstrapError.fallback as AuthFallback);
            authFailed = true;
            throw new Error("auth_failed");
          }
        }
        if (!bootstrapRes.ok || !faqRes.ok) {
          throw new Error("api_failed");
        }

        const bootstrapJson = (await bootstrapRes.json()) as BootstrapResponse;
        const faqJson = (await faqRes.json()) as FaqResponse;
        setBootstrap(bootstrapJson);
        setFaq(faqJson.items || []);
      } catch {
        if (!authFailed) {
          setError("Не удалось загрузить данные mini app. Проверьте API и домен.");
        }
      } finally {
        setLoading(false);
      }
    };

    void load();
  }, [tgId, initData]);

  const openLink = (url: string) => {
    if (webApp?.openLink) {
      webApp.openLink(url);
      return;
    }
    window.open(url, "_blank");
  };

  const createPayment = async (product: "vpn" | "dns" | "pro") => {
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/api/mini/create-payment`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tg_id: tgId,
          product,
          init_data: initData,
          idempotency_key: `${product}-${tgId}`,
        }),
      });

      if (!response.ok) throw new Error("payment_failed");
      const data = (await response.json()) as PaymentResponse;
      setPayment(data);
      setPaymentStage("created");
      setNotice(`Платёж ${data.payment_code} создан. Проверьте кошелёк и подтвердите оплату.`);
      openLink(data.ton_link);
    } catch {
      setError("Не удалось создать платеж. Попробуйте ещё раз.");
    } finally {
      setBusy(false);
    }
  };

  const copyText = async (value: string) => {
    try {
      await navigator.clipboard.writeText(value);
      setNotice("Скопировано в буфер обмена.");
    } catch {
      setError("Не получилось скопировать в буфер обмена.");
    }
  };

  const statusLabel = bootstrap?.status.state === "online" ? "Защита активна" : "Нет активной защиты";
  const stageLabels: Record<PaymentStage, string> = {
    created: "Создано",
    paid: "Оплачено",
    confirmed: "Подтверждено",
    key_issued: "Ключ выдан",
    expired: "Истекло",
  };

  useEffect(() => {
    if (!payment?.payment_code) return;
    let cancelled = false;
    const poll = async () => {
      try {
        const res = await fetch(
          `${API_BASE}/api/mini/payment-status?tg_id=${tgId}&payment_code=${encodeURIComponent(payment.payment_code)}${
            initData ? `&init_data=${encodeURIComponent(initData)}` : ""
          }`
        );
        if (!res.ok) return;
        const data = (await res.json()) as PaymentStatusResponse;
        if (cancelled) return;
        setPaymentStage(data.stage);
        if (data.stage === "key_issued") {
          setNotice("Платёж подтвержден, доступ выдан. Проверьте вкладку «Настройка».");
        }
      } catch {
        // keep silent; polling is best-effort
      }
    };
    void poll();
    const timer = window.setInterval(poll, 5000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [payment?.payment_code, tgId, initData]);

  const activeVpn = bootstrap?.install.vpn_keys?.[0];
  const activeDns = bootstrap?.install.dns?.[0];

  return (
    <main className="min-h-screen px-3 py-4 sm:px-6">
      <section className="app-shell mx-auto max-w-md">
        <header className="mb-4 flex items-center justify-between">
          <div>
            <p className="brand-title">VibeVPN</p>
            <p className="text-xs text-white/60">мини-приложение</p>
          </div>
          <button
            className="icon-btn"
            onClick={() => {
              if (bootstrap?.links.support) openLink(bootstrap.links.support);
            }}
          >
            <Headset size={18} />
          </button>
        </header>

        {loading && <div className="panel p-4 text-sm text-white/70">Загрузка данных...</div>}
        {authFallback && !loading && (
          <div className="panel mb-3">
            <h2 className="section-title">{authFallback.title}</h2>
            <p className="mt-1 text-sm text-white/70">{authFallback.description}</p>
            <button className="primary-btn mt-3 w-full" onClick={() => openLink(authFallback.bot_link)}>
              Открыть бота
            </button>
          </div>
        )}
        {error && !loading && <div className="error-panel mb-3">{error}</div>}
        {notice && !loading && <div className="notice-panel mb-3">{notice}</div>}

        {bootstrap && (
          <div className="space-y-3 pb-22">
            {tab === "store" && (
              <>
                <section className="panel hero-card">
                  <div className="hero-meta">
                    <span className={`status-dot ${bootstrap.status.state === "online" ? "status-online" : "status-offline"}`} />
                    <span className="text-xs uppercase tracking-wide text-white/70">{statusLabel}</span>
                  </div>
                  <h1 className="text-3xl font-semibold leading-tight">
                    {bootstrap.status.active_until ? `Доступ до ${bootstrap.status.active_until}` : "Подключите защиту в 1 тап"}
                  </h1>
                  <p className="text-sm text-white/70">
                    VPN + DNS с реальными статусами, быстрым продлением и P2P покупкой TON.
                  </p>

                  <div className="hero-stats">
                    <div>
                      <p className="hero-k">Баланс</p>
                      <p className="hero-v">{bootstrap.user.balance_ton} TON</p>
                    </div>
                    <div>
                      <p className="hero-k">Рефералы</p>
                      <p className="hero-v">{bootstrap.user.referrals_count}</p>
                    </div>
                    <div>
                      <p className="hero-k">Курс</p>
                      <p className="hero-v">{bootstrap.prices.rate_rub_per_ton} ₽</p>
                    </div>
                  </div>

                  <div className="mt-3 grid grid-cols-2 gap-2">
                    <button disabled={busy} onClick={() => createPayment("pro")} className="primary-btn disabled:opacity-60">
                      {busy ? <LoaderCircle size={16} className="spin" /> : <Sparkles size={16} />}
                      {busy ? "Создаю платёж..." : "Купить PRO"}
                    </button>
                    <button onClick={() => openLink(bootstrap.links.p2p)} className="secondary-btn">
                      <Zap size={16} />
                      Купить TON
                    </button>
                  </div>
                </section>

                {payment && (
                  <section className="panel">
                    <div className="mb-2 flex items-center justify-between">
                      <p className="text-sm">
                        Платеж <b>{payment.payment_code}</b>: {payment.amount_ton} TON (~{payment.amount_rub} ₽)
                      </p>
                      <button className="icon-btn" onClick={() => copyText(payment.payment_code)}>
                        <Copy size={14} />
                      </button>
                    </div>
                    <p className="text-xs text-white/60">Истекает: {payment.expires_at}</p>
                    <div className="payment-steps mt-2">
                      {(["created", "paid", "confirmed", "key_issued"] as PaymentStage[]).map((stage) => {
                        const activeOrder = ["created", "paid", "confirmed", "key_issued"];
                        const currentIdx = activeOrder.indexOf(paymentStage);
                        const stepIdx = activeOrder.indexOf(stage);
                        const active = currentIdx >= stepIdx && paymentStage !== "expired";
                        return (
                          <div key={stage} className={`payment-step ${active ? "payment-step-active" : ""}`}>
                            {stageLabels[stage]}
                          </div>
                        );
                      })}
                    </div>
                    <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2">
                      <button className="primary-btn" onClick={() => openLink(payment.ton_link)}>
                        Оплатить в Tonkeeper
                      </button>
                      <button
                        className="secondary-btn"
                        onClick={() => {
                          setPaymentStage("paid");
                          openLink(payment.bot_check_link);
                        }}
                      >
                        Я оплатил
                      </button>
                    </div>
                  </section>
                )}

                <section className="panel">
                  <div className="mb-2 flex items-center justify-between">
                    <h2 className="section-title">Тарифы</h2>
                    <span className="text-xs text-white/50">реальные цены из API</span>
                  </div>
                  <div className="space-y-2">
                    {bootstrap.prices.plans.map((plan) => (
                        <div key={plan.code} className="plan-row">
                          <div>
                            <p className="font-medium">{plan.title}</p>
                            <p className="text-xs text-white/60">{plan.subtitle}</p>
                          </div>
                          <div className="text-right">
                            <p className="font-semibold">{plan.price_rub} ₽</p>
                            <p className="text-xs text-white/60">{plan.price_ton} TON</p>
                            <button disabled={busy} className="mini-btn mt-1 disabled:opacity-60" onClick={() => createPayment(plan.code)}>
                              Купить
                            </button>
                          </div>
                        </div>
                    ))}
                  </div>
                </section>
              </>
            )}

            {tab === "setup" && (
              <>
                <section className="panel">
                  <h2 className="section-title">Установка и настройка</h2>
                  <p className="text-sm text-white/65">Подключение на текущем устройстве или перенос на другое.</p>
                  <div className="mt-3 space-y-2">
                    <StepRow n="1" text="Откройте ключ в 1 тап." />
                    <StepRow n="2" text="Подтвердите импорт в VPN клиент." />
                    <StepRow n="3" text="Проверьте статус на главной." />
                  </div>
                </section>

                <section className="panel">
                  <div className="space-y-2 text-sm">
                    <InfoRow title="VPN ключ" value={activeVpn ? `Активен до ${activeVpn.expires_at}` : "Пока не выдан"} />
                    <InfoRow title="DNS сервер" value={activeDns?.dns_server_ip || "Будет после покупки DNS"} />
                    <InfoRow title="Текущий IP" value={activeDns?.current_ip || "Не определён"} />
                  </div>
                  <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
                    <button
                      className="primary-btn"
                      onClick={() => (activeVpn ? openLink(activeVpn.access_url) : openLink(bootstrap.links.bot))}
                    >
                      <ShieldCheck size={16} />
                      На этом устройстве
                    </button>
                    <button className="secondary-btn" onClick={() => openLink(bootstrap.links.bot)}>
                      <ExternalLink size={16} />
                      На другом устройстве
                    </button>
                  </div>
                </section>
              </>
            )}

            {tab === "profile" && (
              <>
                <section className="panel">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="avatar">{(bootstrap.user.username?.[0] || "U").toUpperCase()}</div>
                      <div>
                        <p className="font-semibold text-lg">{bootstrap.user.username || "Пользователь"}</p>
                        <p className="text-xs text-white/60">id: {bootstrap.user.telegram_id}</p>
                      </div>
                    </div>
                    <button className="icon-btn" onClick={() => copyText(bootstrap.user.ref_link)}>
                      <Copy size={16} />
                    </button>
                  </div>
                </section>

                <section className="panel">
                  <h2 className="section-title">Профиль и платежи</h2>
                  <div className="mt-2 grid grid-cols-3 gap-2">
                    <Metric title="Баланс" value={`${bootstrap.user.balance_ton} TON`} />
                    <Metric title="Рефералы" value={`${bootstrap.user.referrals_count}`} />
                    <Metric title="Статус" value={bootstrap.status.state} />
                  </div>
                  <div className="mt-3 ref-box">
                    <Link2 size={14} />
                    <span className="truncate">{bootstrap.user.ref_link}</span>
                  </div>
                </section>
              </>
            )}

            {tab === "support" && (
              <>
                <section className="panel">
                  <h2 className="section-title">Поддержка</h2>
                  <p className="text-sm text-white/65">FAQ и быстрый переход в чат поддержки.</p>
                  <button className="primary-btn mt-3 w-full" onClick={() => openLink(bootstrap.links.support)}>
                    Написать в поддержку
                  </button>
                </section>

                <section className="panel">
                  <div className="space-y-2">
                    {faq.map((item) => (
                      <div key={item.q} className="faq-row">
                        <div className="mt-0.5 text-emerald-300">
                          <BadgeHelp size={16} />
                        </div>
                        <div>
                          <p className="text-sm font-medium">{item.q}</p>
                          <p className="text-xs text-white/65">{item.a}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </section>
              </>
            )}
          </div>
        )}

        <nav className="bottom-nav">
          <NavItem active={tab === "store"} onClick={() => setTab("store")} icon={<House size={18} />} label="Главная" />
          <NavItem active={tab === "setup"} onClick={() => setTab("setup")} icon={<Settings size={18} />} label="Настройка" />
          <NavItem active={tab === "profile"} onClick={() => setTab("profile")} icon={<CircleUserRound size={18} />} label="Профиль" />
          <NavItem active={tab === "support"} onClick={() => setTab("support")} icon={<Headset size={18} />} label="Поддержка" />
        </nav>
      </section>
    </main>
  );
}

function NavItem({
  active,
  onClick,
  icon,
  label,
}: {
  active: boolean;
  onClick: () => void;
  icon: ReactNode;
  label: string;
}) {
  return (
    <button onClick={onClick} className={`nav-item ${active ? "nav-item-active" : ""}`}>
      {icon}
      <span>{label}</span>
    </button>
  );
}

function StepRow({ n, text }: { n: string; text: string }) {
  return (
    <div className="step-row">
      <span className="step-badge">{n}</span>
      <span className="text-sm">{text}</span>
    </div>
  );
}

function InfoRow({ title, value }: { title: string; value: string }) {
  return (
    <div className="info-row">
      <span className="text-white/70">{title}</span>
      <span className="font-medium">{value}</span>
    </div>
  );
}

function Metric({ title, value }: { title: string; value: string }) {
  return (
    <div className="metric">
      <p className="text-[11px] uppercase tracking-wide text-white/55">{title}</p>
      <p className="mt-1 text-sm font-semibold">{value}</p>
    </div>
  );
}
