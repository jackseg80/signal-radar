import React from 'react';
import { motion } from 'framer-motion';
import { BookOpen, Layers, Zap, ShieldCheck, Target, TrendingUp, Calendar, ArrowRight } from 'lucide-react';
import RSI2Visualizer from '../components/strategies/RSI2Visualizer';
import IBSVisualizer from '../components/strategies/IBSVisualizer';
import TOMVisualizer from '../components/strategies/TOMVisualizer';

export default function Strategies() {
  return (
    <div className="space-y-12 pb-20 animate-fade-in">
      {/* Hero Section */}
      <section className="text-center space-y-4 max-w-3xl mx-auto py-8">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-green-500/10 text-green-400 border border-green-500/20 text-[10px] font-bold uppercase tracking-widest">
          <BookOpen size={14} />
          Centre d'apprentissage
        </div>
        <h1 className="text-4xl md:text-5xl font-black text-white tracking-tighter" style={{ fontFamily: "'Space Grotesk', sans-serif" }}>
          L'Anatomie des <span className="text-green-400">Stratégies</span>
        </h1>
        <p className="text-lg text-[--text-muted] leading-relaxed">
          Comprendre la logique mathématique derrière chaque signal pour trader avec conviction et discipline.
        </p>
      </section>

      {/* Philosophy */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
         {[
           { icon: <Layers className="text-blue-400" />, title: "Indépendance", desc: "Chaque stratégie exploite une anomalie différente. Elles ne sont pas liées." },
           { icon: <Zap className="text-amber-400" />, title: "Confluence", desc: "Quand plusieurs stratégies s'alignent, la probabilité de succès augmente." },
           { icon: <ShieldCheck className="text-green-400" />, title: "Survie", desc: "Le filtre de tendance SMA200 est notre bouclier contre les marchés baissiers." }
         ].map((item, i) => (
           <motion.div 
             key={i}
             initial={{ opacity: 0, y: 20 }}
             whileInView={{ opacity: 1, y: 0 }}
             viewport={{ once: true }}
             transition={{ delay: i * 0.1 }}
             className="glass-card p-6 rounded-2xl border border-white/5 space-y-3"
           >
             <div className="p-2 w-fit rounded-lg bg-white/5">{item.icon}</div>
             <h3 className="font-bold text-white uppercase text-sm tracking-widest">{item.title}</h3>
             <p className="text-xs text-[--text-muted] leading-relaxed">{item.desc}</p>
           </motion.div>
         ))}
      </div>

      {/* RSI(2) Section */}
      <section className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
        <div className="space-y-6">
          <div className="space-y-2">
            <h2 className="text-3xl font-bold text-white flex items-center gap-3">
              <span className="text-green-400">01.</span> RSI(2) Mean Reversion
            </h2>
            <p className="text-[--text-secondary] leading-relaxed">
              Inspirée par Larry Connors, cette stratégie repose sur l'idée que les actions en tendance haussière qui subissent une correction brutale (pullback) ont tendance à rebondir très vite vers leur moyenne.
            </p>
          </div>
          
          <div className="space-y-4">
             <div className="flex gap-4 p-4 rounded-xl bg-white/5 border border-white/5">
                <TrendingUp size={24} className="text-green-400 shrink-0" />
                <div>
                  <h4 className="text-sm font-bold text-white uppercase">Condition de Tendance</h4>
                  <p className="text-xs text-[--text-muted]">L'actif doit être au-dessus de sa moyenne mobile 200 jours (SMA 200).</p>
                </div>
             </div>
             <div className="flex gap-4 p-4 rounded-xl bg-white/5 border border-white/5">
                <ArrowRight size={24} className="text-amber-400 shrink-0" />
                <div>
                  <h4 className="text-sm font-bold text-white uppercase">Seuil d'Entrée</h4>
                  <p className="text-xs text-[--text-muted]">Achat quand le RSI sur 2 jours descend sous 10.</p>
                </div>
             </div>
             <div className="flex gap-4 p-4 rounded-xl bg-white/5 border border-white/5">
                <Target size={24} className="text-blue-400 shrink-0" />
                <div>
                  <h4 className="text-sm font-bold text-white uppercase">Cible de Sortie</h4>
                  <p className="text-xs text-[--text-muted]">Vente quand le prix remonte au-dessus de sa moyenne mobile 5 jours (SMA 5).</p>
                </div>
             </div>
          </div>
        </div>
        <RSI2Visualizer />
      </section>

      {/* IBS Section */}
      <section className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center py-12 border-t border-white/5">
        <div className="order-2 lg:order-1">
          <IBSVisualizer />
        </div>
        <div className="space-y-6 order-1 lg:order-2">
          <div className="space-y-2 text-right">
            <h2 className="text-3xl font-bold text-white flex items-center gap-3 justify-end">
              Internal Bar Strength <span className="text-green-400">.02</span>
            </h2>
            <p className="text-[--text-secondary] leading-relaxed">
              L'IBS exploite la "force interne" d'une bougie quotidienne. C'est un indicateur de survente extrême à très court terme (24h-48h).
            </p>
          </div>
          
          <div className="space-y-4">
             <div className="p-4 rounded-xl bg-white/5 border border-white/5 text-right">
                <h4 className="text-sm font-bold text-white uppercase">Calcul Mathématique</h4>
                <code className="text-[10px] text-green-400 font-mono">(Clôture - Bas) / (Haut - Bas)</code>
             </div>
             <p className="text-xs text-[--text-muted] leading-relaxed text-right">
               On achète quand l'IBS est inférieur à 0.20, ce qui signifie que l'actif a fini sa journée tout en bas de son range. Historiquement, cela précède souvent un rebond correctif immédiat le lendemain.
             </p>
          </div>
        </div>
      </section>

      {/* TOM Section */}
      <section className="space-y-8 py-12 border-t border-white/5">
        <div className="max-w-3xl space-y-4">
          <h2 className="text-3xl font-bold text-white flex items-center gap-3">
            <Calendar className="text-green-400" size={32} />
            <span className="text-green-400">03.</span> Turn of the Month (TOM)
          </h2>
          <p className="text-[--text-secondary] leading-relaxed">
            Une anomalie calendaire persistante depuis des décennies. Les flux de capitaux (fonds de pension, virements automatiques de salaires) créent une pression acheteuse systématique à chaque fin de mois.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-start">
          <div className="space-y-6">
             <div className="space-y-4">
                <h4 className="text-lg font-bold text-white uppercase tracking-tight">Mécanique de la Fenêtre</h4>
                <ul className="space-y-4">
                  <li className="flex gap-4 p-4 rounded-xl bg-white/5 border border-white/5">
                    <div className="w-8 h-8 rounded-full bg-green-500/10 text-green-400 flex items-center justify-center font-bold shrink-0">1</div>
                    <p className="text-sm text-[--text-muted]">On identifie les <strong>5 derniers jours de bourse</strong> du mois actuel.</p>
                  </li>
                  <li className="flex gap-4 p-4 rounded-xl bg-white/5 border border-white/5">
                    <div className="w-8 h-8 rounded-full bg-blue-500/10 text-blue-400 flex items-center justify-center font-bold shrink-0">2</div>
                    <p className="text-sm text-[--text-muted]">On sort de position après les <strong>3 premiers jours de bourse</strong> du mois suivant.</p>
                  </li>
                  <li className="flex gap-4 p-4 rounded-xl bg-white/5 border border-white/5">
                    <div className="w-8 h-8 rounded-full bg-amber-500/10 text-amber-400 flex items-center justify-center font-bold shrink-0">3</div>
                    <p className="text-sm text-[--text-muted]">Cette fenêtre capture l'effet de "Window Dressing" et les réallocations automatiques institutionnelles.</p>
                  </li>
                </ul>
             </div>
          </div>
          <TOMVisualizer />
        </div>
      </section>
    </div>
  );
}
