import { ExternalLink, ShieldCheck } from "lucide-react";
import { InfoRow, StepRow } from "../UiBits";
import { BootstrapResponse } from "../../types";

export function SetupTab({
  bootstrap,
  activeVpn,
  activeDns,
  onOpenLink,
}: {
  bootstrap: BootstrapResponse;
  activeVpn?: { access_url: string; expires_at: string };
  activeDns?: { dns_server_ip: string; current_ip: string | null };
  onOpenLink: (url: string) => void;
}) {
  return (
    <>
      <section className="panel">
        <h2 className="section-title">РЈСЃС‚Р°РЅРѕРІРєР° Рё РЅР°СЃС‚СЂРѕР№РєР°</h2>
        <p className="text-sm text-white/65">РџРѕРґРєР»СЋС‡РµРЅРёРµ РЅР° С‚РµРєСѓС‰РµРј СѓСЃС‚СЂРѕР№СЃС‚РІРµ РёР»Рё РїРµСЂРµРЅРѕСЃ РЅР° РґСЂСѓРіРѕРµ.</p>
        <div className="mt-3 space-y-2">
          <StepRow n="1" text="РћС‚РєСЂРѕР№С‚Рµ РєР»СЋС‡ РІ 1 С‚Р°Рї." />
          <StepRow n="2" text="РџРѕРґС‚РІРµСЂРґРёС‚Рµ РёРјРїРѕСЂС‚ РІ VPN РєР»РёРµРЅС‚." />
          <StepRow n="3" text="РџСЂРѕРІРµСЂСЊС‚Рµ СЃС‚Р°С‚СѓСЃ РЅР° РіР»Р°РІРЅРѕР№." />
        </div>
      </section>

      <section className="panel">
        <div className="space-y-2 text-sm">
          <InfoRow title="VPN РєР»СЋС‡" value={activeVpn ? `РђРєС‚РёРІРµРЅ РґРѕ ${activeVpn.expires_at}` : "РџРѕРєР° РЅРµ РІС‹РґР°РЅ"} />
          <InfoRow title="DNS СЃРµСЂРІРµСЂ" value={activeDns?.dns_server_ip || "Р‘СѓРґРµС‚ РїРѕСЃР»Рµ РїРѕРєСѓРїРєРё DNS"} />
          <InfoRow title="РўРµРєСѓС‰РёР№ IP" value={activeDns?.current_ip || "РќРµ РѕРїСЂРµРґРµР»С‘РЅ"} />
        </div>
        <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
          <button className="primary-btn" onClick={() => (activeVpn ? onOpenLink(activeVpn.access_url) : onOpenLink(bootstrap.links.bot))}>
            <ShieldCheck size={16} />
            РќР° СЌС‚РѕРј СѓСЃС‚СЂРѕР№СЃС‚РІРµ
          </button>
          <button className="secondary-btn" onClick={() => onOpenLink(bootstrap.links.bot)}>
            <ExternalLink size={16} />
            РќР° РґСЂСѓРіРѕРј СѓСЃС‚СЂРѕР№СЃС‚РІРµ
          </button>
        </div>
      </section>
    </>
  );
}
