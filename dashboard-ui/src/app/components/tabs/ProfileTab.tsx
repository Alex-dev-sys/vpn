import { Copy } from "lucide-react";
import { Metric } from "../UiBits";
import { BootstrapResponse } from "../../types";

export function ProfileTab({
  bootstrap,
  onCopyRefLink,
}: {
  bootstrap: BootstrapResponse;
  onCopyRefLink: () => void;
}) {
  return (
    <>
      <section className="panel">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="avatar">{(bootstrap.user.username?.[0] || "U").toUpperCase()}</div>
            <div>
              <p className="font-semibold text-lg">{bootstrap.user.username || "РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ"}</p>
              <p className="text-xs text-white/60">id: {bootstrap.user.telegram_id}</p>
            </div>
          </div>
          <button className="icon-btn" onClick={onCopyRefLink}>
            <Copy size={16} />
          </button>
        </div>
      </section>

      <section className="panel">
        <h2 className="section-title">РџСЂРѕС„РёР»СЊ Рё РїР»Р°С‚РµР¶Рё</h2>
        <div className="mt-2 grid grid-cols-3 gap-2">
          <Metric title="Р‘Р°Р»Р°РЅСЃ" value={`${bootstrap.user.balance_ton} TON`} />
          <Metric title="Р РµС„РµСЂР°Р»С‹" value={`${bootstrap.user.referrals_count}`} />
          <Metric title="РЎС‚Р°С‚СѓСЃ" value={bootstrap.status.state} />
        </div>
        <div className="mt-3 ref-box">
          <span className="truncate">{bootstrap.user.ref_link}</span>
        </div>
      </section>
    </>
  );
}
