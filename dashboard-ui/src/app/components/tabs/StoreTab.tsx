import { LoaderCircle, Sparkles, Zap } from "lucide-react";
import { PaymentCard } from "../PaymentCard";
import { P2PPanel } from "../P2PPanel";
import {
  BootstrapResponse,
  P2POrderResponse,
  P2POrderStatusResponse,
  P2PQuoteResponse,
  PaymentResponse,
  PaymentStage,
} from "../../types";

export function StoreTab({
  bootstrap,
  statusLabel,
  busy,
  payment,
  paymentStage,
  p2pAmountTon,
  p2pWalletAddress,
  p2pBusy,
  p2pQuote,
  p2pOrder,
  p2pStatus,
  onCreatePayment,
  onShowP2PHint,
  onP2PAmountChange,
  onP2PWalletChange,
  onP2PQuote,
  onP2PCreateOrder,
  onP2PMarkPaid,
  onOpenLink,
  onCopyPaymentCode,
  onPaymentMarkPaid,
}: {
  bootstrap: BootstrapResponse;
  statusLabel: string;
  busy: boolean;
  payment: PaymentResponse | null;
  paymentStage: PaymentStage;
  p2pAmountTon: string;
  p2pWalletAddress: string;
  p2pBusy: boolean;
  p2pQuote: P2PQuoteResponse | null;
  p2pOrder: P2POrderResponse | null;
  p2pStatus: P2POrderStatusResponse | null;
  onCreatePayment: (product: "vpn" | "dns" | "pro") => void;
  onShowP2PHint: () => void;
  onP2PAmountChange: (value: string) => void;
  onP2PWalletChange: (value: string) => void;
  onP2PQuote: () => void;
  onP2PCreateOrder: () => void;
  onP2PMarkPaid: () => void;
  onOpenLink: (url: string) => void;
  onCopyPaymentCode: () => void;
  onPaymentMarkPaid: () => void;
}) {
  return (
    <>
      <section className="panel hero-card">
        <div className="hero-meta">
          <span className={`status-dot ${bootstrap.status.state === "online" ? "status-online" : "status-offline"}`} />
          <span className="text-xs uppercase tracking-wide text-white/70">{statusLabel}</span>
        </div>
        <h1 className="text-3xl font-semibold leading-tight">
          {bootstrap.status.active_until ? `Р”РѕСЃС‚СѓРї РґРѕ ${bootstrap.status.active_until}` : "РџРѕРґРєР»СЋС‡РёС‚Рµ Р·Р°С‰РёС‚Сѓ РІ 1 С‚Р°Рї"}
        </h1>
        <p className="text-sm text-white/70">
          VPN + DNS СЃ СЂРµР°Р»СЊРЅС‹РјРё СЃС‚Р°С‚СѓСЃР°РјРё, Р±С‹СЃС‚СЂС‹Рј РїСЂРѕРґР»РµРЅРёРµРј Рё P2P РїРѕРєСѓРїРєРѕР№ TON.
        </p>

        <div className="hero-stats">
          <div>
            <p className="hero-k">Р‘Р°Р»Р°РЅСЃ</p>
            <p className="hero-v">{bootstrap.user.balance_ton} TON</p>
          </div>
          <div>
            <p className="hero-k">Р РµС„РµСЂР°Р»С‹</p>
            <p className="hero-v">{bootstrap.user.referrals_count}</p>
          </div>
          <div>
            <p className="hero-k">РљСѓСЂСЃ</p>
            <p className="hero-v">{bootstrap.prices.rate_rub_per_ton} в‚Ѕ</p>
          </div>
        </div>

        <div className="mt-3 grid grid-cols-2 gap-2">
          <button disabled={busy} onClick={() => onCreatePayment("pro")} className="primary-btn disabled:opacity-60">
            {busy ? <LoaderCircle size={16} className="spin" /> : <Sparkles size={16} />}
            {busy ? "РЎРѕР·РґР°СЋ РїР»Р°С‚С‘Р¶..." : "РљСѓРїРёС‚СЊ PRO"}
          </button>
          <button onClick={onShowP2PHint} className="secondary-btn">
            <Zap size={16} />
            РљСѓРїРёС‚СЊ TON Р·РґРµСЃСЊ
          </button>
        </div>
      </section>

      <P2PPanel
        p2pAmountTon={p2pAmountTon}
        p2pWalletAddress={p2pWalletAddress}
        p2pBusy={p2pBusy}
        p2pQuote={p2pQuote}
        p2pOrder={p2pOrder}
        p2pStatus={p2pStatus}
        onAmountChange={onP2PAmountChange}
        onWalletChange={onP2PWalletChange}
        onQuote={onP2PQuote}
        onCreateOrder={onP2PCreateOrder}
        onMarkPaid={onP2PMarkPaid}
        onOpenTx={onOpenLink}
      />

      {payment && (
        <PaymentCard
          payment={payment}
          paymentStage={paymentStage}
          onCopyCode={onCopyPaymentCode}
          onOpenPay={() => onOpenLink(payment.ton_link)}
          onMarkPaid={onPaymentMarkPaid}
        />
      )}

      <section className="panel">
        <div className="mb-2 flex items-center justify-between">
          <h2 className="section-title">РўР°СЂРёС„С‹</h2>
          <span className="text-xs text-white/50">СЂРµР°Р»СЊРЅС‹Рµ С†РµРЅС‹ РёР· API</span>
        </div>
        <div className="space-y-2">
          {bootstrap.prices.plans.map((plan) => (
            <div key={plan.code} className="plan-row">
              <div>
                <p className="font-medium">{plan.title}</p>
                <p className="text-xs text-white/60">{plan.subtitle}</p>
              </div>
              <div className="text-right">
                <p className="font-semibold">{plan.price_rub} в‚Ѕ</p>
                <p className="text-xs text-white/60">{plan.price_ton} TON</p>
                <button disabled={busy} className="mini-btn mt-1 disabled:opacity-60" onClick={() => onCreatePayment(plan.code)}>
                  РљСѓРїРёС‚СЊ
                </button>
              </div>
            </div>
          ))}
        </div>
      </section>
    </>
  );
}
