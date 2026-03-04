import { LoaderCircle } from "lucide-react";
import { P2POrderResponse, P2POrderStatusResponse, P2PQuoteResponse } from "../types";

export function P2PPanel({
  p2pAmountTon,
  p2pWalletAddress,
  p2pBusy,
  p2pQuote,
  p2pOrder,
  p2pStatus,
  onAmountChange,
  onWalletChange,
  onQuote,
  onCreateOrder,
  onMarkPaid,
  onOpenTx,
}: {
  p2pAmountTon: string;
  p2pWalletAddress: string;
  p2pBusy: boolean;
  p2pQuote: P2PQuoteResponse | null;
  p2pOrder: P2POrderResponse | null;
  p2pStatus: P2POrderStatusResponse | null;
  onAmountChange: (value: string) => void;
  onWalletChange: (value: string) => void;
  onQuote: () => void;
  onCreateOrder: () => void;
  onMarkPaid: () => void;
  onOpenTx: (url: string) => void;
}) {
  return (
    <section className="panel">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="section-title">P2P: TON за RUB (в Mini App)</h2>
        <span className="text-xs text-white/60">без перехода в чат</span>
      </div>
      <div className="space-y-2">
        <input
          className="text-input"
          value={p2pAmountTon}
          onChange={(e) => onAmountChange(e.target.value)}
          placeholder="Количество TON, например 5"
        />
        <input
          className="text-input"
          value={p2pWalletAddress}
          onChange={(e) => onWalletChange(e.target.value)}
          placeholder="Ваш TON-кошелёк (UQ...)"
        />
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          <button className="secondary-btn" disabled={p2pBusy} onClick={onQuote}>
            {p2pBusy ? <LoaderCircle size={16} className="spin" /> : null}
            Рассчитать
          </button>
          <button className="primary-btn" disabled={p2pBusy || !p2pWalletAddress.trim()} onClick={onCreateOrder}>
            {p2pBusy ? <LoaderCircle size={16} className="spin" /> : null}
            Создать заявку
          </button>
        </div>
      </div>

      {p2pQuote && (
        <div className="p2p-box mt-2">
          <p className="text-sm">
            К оплате: <b>{p2pQuote.amount_rub} ₽</b> за {p2pQuote.amount_ton} TON
          </p>
          <p className="text-xs text-white/65">
            Курс: {p2pQuote.rate_rub_per_ton.toFixed(2)} ₽/TON (маржа {p2pQuote.margin_percent}%)
          </p>
        </div>
      )}

      {p2pOrder && (
        <div className="p2p-box mt-2">
          <p className="text-sm">
            Заказ <b>#{p2pOrder.order_id}</b>: {p2pOrder.amount_ton} TON за {p2pOrder.amount_rub} ₽
          </p>
          <p className="text-xs text-white/65">Кошелёк: {p2pOrder.wallet_masked}</p>
          <div className="mt-2 rounded-xl border border-white/10 p-2 text-sm">
            <p>
              🏦 Банк: <b>{p2pOrder.payment_requisites.bank || "—"}</b>
            </p>
            <p>
              💳 Карта: <b>{p2pOrder.payment_requisites.card || "—"}</b>
            </p>
            {p2pOrder.payment_requisites.sbp_phone ? (
              <p>
                📱 СБП: <b>{p2pOrder.payment_requisites.sbp_phone}</b>
              </p>
            ) : null}
          </div>
          <button className="primary-btn mt-2 w-full" disabled={p2pBusy} onClick={onMarkPaid}>
            Я оплатил
          </button>
        </div>
      )}

      {p2pStatus && (
        <div className="p2p-box mt-2">
          <p className="text-sm">
            Статус: <b>{p2pStatus.stage}</b>
          </p>
          {p2pStatus.tx_link ? (
            <button className="secondary-btn mt-2 w-full" onClick={() => onOpenTx(p2pStatus.tx_link || "")}>
              Открыть транзакцию
            </button>
          ) : null}
          {p2pStatus.cancel_reason ? <p className="text-xs mt-1 text-rose-200">{p2pStatus.cancel_reason}</p> : null}
        </div>
      )}
    </section>
  );
}
