import React from 'react';
import { X, BookOpen, Layers, Zap, ShieldCheck, Target } from 'lucide-react';

export default function GuideModal({ isOpen, onClose }) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fade-in">
      <div className="relative w-full max-w-2xl max-h-[90vh] overflow-y-auto glass-card rounded-2xl shadow-2xl border border-white/10 flex flex-col">
        {/* Header */}
        <div className="sticky top-0 z-10 flex items-center justify-between p-6 border-b border-white/5 bg-[--bg-card]/95 backdrop-blur-md">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-green-500/10 text-green-400">
              <BookOpen size={24} />
            </div>
            <div>
              <h2 className="text-xl font-bold text-white tracking-tight">Guide Stratégique</h2>
              <p className="text-xs text-[--text-muted]">Comprendre et exploiter les signaux</p>
            </div>
          </div>
          <button 
            onClick={onClose}
            className="p-2 rounded-full hover:bg-white/5 text-[--text-muted] hover:text-white transition-colors cursor-pointer"
          >
            <X size={20} />
          </button>
        </div>

        {/* Content */}
        <div className="p-8 space-y-8">
          {/* Section 1: Philosophie */}
          <section className="space-y-4">
            <div className="flex items-center gap-2 text-green-400 font-bold uppercase tracking-wider text-xs">
              <Layers size={14} />
              <span>Indépendance & Diversification</span>
            </div>
            <p className="text-sm text-[--text-secondary] leading-relaxed">
              Le système exécute 3 stratégies en parallèle (**RSI2, IBS, TOM**). Elles sont totalement <strong>indépendantes</strong>. 
              L'objectif est la diversification : si une stratégie est calme ou en perte temporaire, les autres peuvent compenser.
            </p>
          </section>

          {/* Section 2: Confluence */}
          <section className="space-y-4">
            <div className="flex items-center gap-2 text-amber-400 font-bold uppercase tracking-wider text-xs">
              <Zap size={14} />
              <span>Le concept de Confluence</span>
            </div>
            <p className="text-sm text-[--text-secondary] leading-relaxed">
              Une <strong>confluence</strong> se produit quand plusieurs stratégies donnent un signal sur le même actif (ex: RSI2 &lt; 10 + période TOM). 
              Ces signaux sont rares mais statistiquement plus puissants. Cependant, n'attendez pas de confluence pour agir : chaque stratégie est rentable seule.
            </p>
          </section>

          {/* Section 3: Filtres */}
          <section className="space-y-4">
            <div className="flex items-center gap-2 text-blue-400 font-bold uppercase tracking-wider text-xs">
              <ShieldCheck size={14} />
              <span>Filtre de Tendance (SKIP)</span>
            </div>
            <p className="text-sm text-[--text-secondary] leading-relaxed">
              Pour le RSI(2) et l'IBS, nous n'achetons que si le prix est au-dessus de sa <strong>Moyenne Mobile 200 jours</strong>. 
              Si un actif est survendu mais en tendance baissière, le système affiche <strong>SKIP</strong>. C'est une sécurité vitale pour éviter de "ramasser un couteau qui tombe".
            </p>
          </section>

          {/* Section 4: Gestion du risque */}
          <section className="space-y-4">
            <div className="flex items-center gap-2 text-purple-400 font-bold uppercase tracking-wider text-xs">
              <Target size={14} />
              <span>Gestion du Risque & Sorties</span>
            </div>
            <div className="bg-white/5 rounded-xl p-4 space-y-3 border border-white/5">
              <div className="flex gap-3">
                <div className="w-1.5 h-1.5 rounded-full bg-green-500 mt-1.5 shrink-0" />
                <p className="text-xs text-[--text-secondary]"><strong>Taille :</strong> Ne risquez pas tout sur un signal. Répartissez votre capital (ex: 20% par position).</p>
              </div>
              <div className="flex gap-3">
                <div className="w-1.5 h-1.5 rounded-full bg-green-500 mt-1.5 shrink-0" />
                <p className="text-xs text-[--text-secondary]"><strong>Sortie :</strong> Chaque stratégie a sa propre règle. Sortez dès que l'objectif est atteint ou que le signal d'exit apparaît, sans état d'âme.</p>
              </div>
              <div className="flex gap-3">
                <div className="w-1.5 h-1.5 rounded-full bg-green-500 mt-1.5 shrink-0" />
                <p className="text-xs text-[--text-secondary]"><strong>Temps :</strong> Les signaux sont calculés sur la clôture quotidienne (Daily). Le scanner tourne une fois par jour.</p>
              </div>
            </div>
          </section>
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-white/5 bg-white/[0.02] text-center">
          <button 
            onClick={onClose}
            className="px-6 py-2 bg-green-500/10 hover:bg-green-500/20 text-green-400 border border-green-500/30 rounded-lg text-sm font-bold transition-all cursor-pointer"
          >
            J'ai compris
          </button>
        </div>
      </div>
    </div>
  );
}
