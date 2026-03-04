"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { CircleUserRound, Headset, House, Settings } from "lucide-react";
import { NavItem } from "./components/UiBits";
import { ProfileTab } from "./components/tabs/ProfileTab";
import { SetupTab } from "./components/tabs/SetupTab";
import { StoreTab } from "./components/tabs/StoreTab";
import { SupportTab } from "./components/tabs/SupportTab";
import {
  AuthFallback,
  BootstrapResponse,
  FaqResponse,
  P2POrderResponse,
  P2POrderStatusResponse,
  P2PQuoteResponse,
  PaymentResponse,
  PaymentStage,
  PaymentStatusResponse,
  TabKey,
  TelegramWebApp,
} from "./types";

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
  const [p2pAmountTon, setP2pAmountTon] = useState<string>("1");
  const [p2pWalletAddress, setP2pWalletAddress] = useState<string>("");
  const [p2pBusy, setP2pBusy] = useState(false);
  const [p2pQuote, setP2pQuote] = useState<P2PQuoteResponse | null>(null);
  const [p2pOrder, setP2pOrder] = useState<P2POrderResponse | null>(null);
  const [p2pStatus, setP2pStatus] = useState<P2POrderStatusResponse | null>(null);

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
        // polling best-effort
      }
    };
    void poll();
    const timer = window.setInterval(poll, 5000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [payment?.payment_code, tgId, initData]);

  const pollP2PStatus = useCallback(
    async (orderId: number) => {
      const res = await fetch(
        `${API_BASE}/api/mini/p2p/order-status?tg_id=${tgId}&order_id=${orderId}${
          initData ? `&init_data=${encodeURIComponent(initData)}` : ""
        }`
      );
      if (!res.ok) return;
      const data = (await res.json()) as P2POrderStatusResponse;
      setP2pStatus(data);
    },
    [tgId, initData]
  );

  const fetchP2PQuote = async () => {
    setP2pBusy(true);
    setError(null);
    try {
      const amount = Number(p2pAmountTon);
      const res = await fetch(`${API_BASE}/api/mini/p2p/quote`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tg_id: tgId, init_data: initData, amount_ton: amount }),
      });
      const body = await res.json().catch(() => null);
      if (!res.ok) {
        throw new Error(body?.detail || "quote_failed");
      }
      setP2pQuote(body as P2PQuoteResponse);
      setNotice("Расчёт обновлён. Теперь можно создать заявку.");
    } catch (e) {
      setError(`Не удалось рассчитать P2P: ${e instanceof Error ? e.message : "ошибка"}`);
    } finally {
      setP2pBusy(false);
    }
  };

  const createP2POrder = async () => {
    setP2pBusy(true);
    setError(null);
    try {
      const amount = Number(p2pAmountTon);
      const res = await fetch(`${API_BASE}/api/mini/p2p/create-order`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tg_id: tgId,
          init_data: initData,
          amount_ton: amount,
          wallet_address: p2pWalletAddress.trim(),
        }),
      });
      const body = await res.json().catch(() => null);
      if (!res.ok) {
        throw new Error(body?.detail || "create_order_failed");
      }
      setP2pOrder(body as P2POrderResponse);
      setP2pStatus(null);
      setNotice(`P2P заявка #${(body as P2POrderResponse).order_id} создана.`);
    } catch (e) {
      setError(`Не удалось создать P2P заявку: ${e instanceof Error ? e.message : "ошибка"}`);
    } finally {
      setP2pBusy(false);
    }
  };

  const markP2PPaid = async () => {
    if (!p2pOrder) return;
    setP2pBusy(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/mini/p2p/mark-paid`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tg_id: tgId, init_data: initData, order_id: p2pOrder.order_id }),
      });
      const body = await res.json().catch(() => null);
      if (!res.ok) throw new Error(body?.detail || "mark_paid_failed");
      setNotice("Заявка отправлена на подтверждение. Ожидайте перевода TON.");
      await pollP2PStatus(p2pOrder.order_id);
    } catch (e) {
      setError(`Не удалось подтвердить оплату: ${e instanceof Error ? e.message : "ошибка"}`);
    } finally {
      setP2pBusy(false);
    }
  };

  useEffect(() => {
    if (!p2pOrder?.order_id) return;
    let cancelled = false;
    const tick = async () => {
      if (cancelled) return;
      await pollP2PStatus(p2pOrder.order_id);
    };
    void tick();
    const timer = window.setInterval(tick, 5000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [p2pOrder?.order_id, pollP2PStatus]);

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
              <StoreTab
                bootstrap={bootstrap}
                statusLabel={statusLabel}
                busy={busy}
                payment={payment}
                paymentStage={paymentStage}
                p2pAmountTon={p2pAmountTon}
                p2pWalletAddress={p2pWalletAddress}
                p2pBusy={p2pBusy}
                p2pQuote={p2pQuote}
                p2pOrder={p2pOrder}
                p2pStatus={p2pStatus}
                onCreatePayment={createPayment}
                onShowP2PHint={() => setNotice("Заполните форму P2P ниже: сумма TON и ваш кошелёк.")}
                onP2PAmountChange={setP2pAmountTon}
                onP2PWalletChange={setP2pWalletAddress}
                onP2PQuote={fetchP2PQuote}
                onP2PCreateOrder={createP2POrder}
                onP2PMarkPaid={markP2PPaid}
                onOpenLink={openLink}
                onCopyPaymentCode={() => {
                  if (payment) void copyText(payment.payment_code);
                }}
                onPaymentMarkPaid={() => {
                  if (!payment) return;
                  setPaymentStage("paid");
                  openLink(payment.bot_check_link);
                }}
              />
            )}

            {tab === "setup" && (
              <SetupTab
                bootstrap={bootstrap}
                activeVpn={activeVpn}
                activeDns={activeDns}
                onOpenLink={openLink}
              />
            )}

            {tab === "profile" && (
              <ProfileTab
                bootstrap={bootstrap}
                onCopyRefLink={() => {
                  void copyText(bootstrap.user.ref_link);
                }}
              />
            )}

            {tab === "support" && <SupportTab bootstrap={bootstrap} faq={faq} onOpenLink={openLink} />}
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
