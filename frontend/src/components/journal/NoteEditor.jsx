import { useState } from 'react';
import { Smile, Frown, Meh, Tag, Save, X } from 'lucide-react';

const SENTIMENTS = [
  { value: 'happy', icon: <Smile size={14} />, color: 'text-green-400', label: 'Confiant' },
  { value: 'neutral', icon: <Meh size={14} />, color: 'text-amber-400', label: 'Neutre' },
  { value: 'sad', icon: <Frown size={14} />, color: 'text-red-400', label: 'Stressé' },
];

const PRESET_TAGS = ['#FOMO', '#Discipline', '#Fatigue', '#PlanRespecté', '#News', '#Slippage'];

export default function NoteEditor({ notes, tags, sentiment, source, id, onSaved }) {
  const [editing, setEditing] = useState(false);
  const [formData, setFormData] = useState({
    notes: notes || '',
    tags: tags || '',
    sentiment: sentiment || 'neutral'
  });
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    try {
      const { api } = await import('../../api/client');
      if (source === 'paper') {
        await api.journalUpdatePaper(id, formData);
      } else {
        await api.journalUpdateLive(id, formData);
      }
      setEditing(false);
      onSaved?.();
    } catch (err) {
      console.error('Failed to save journal entry:', err);
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    setFormData({
      notes: notes || '',
      tags: tags || '',
      sentiment: sentiment || 'neutral'
    });
    setEditing(false);
  };

  const toggleTag = (tag) => {
    const currentTags = formData.tags.split(' ').filter(t => t.startsWith('#'));
    if (currentTags.includes(tag)) {
      setFormData({ ...formData, tags: currentTags.filter(t => t !== tag).join(' ') });
    } else {
      setFormData({ ...formData, tags: [...currentTags, tag].join(' ') });
    }
  };

  if (!editing) {
    const currentSentiment = SENTIMENTS.find(s => s.value === (sentiment || 'neutral'));
    return (
      <div className="space-y-2">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 space-y-1">
            {notes ? (
              <p className="text-xs text-[--text-secondary] italic leading-relaxed">{notes}</p>
            ) : (
              <p className="text-xs text-[--text-muted]">Aucune note.</p>
            )}
            
            {(tags || sentiment) && (
              <div className="flex flex-wrap items-center gap-2 pt-1">
                {sentiment && (
                  <span className={`flex items-center gap-1 text-[10px] font-bold px-1.5 py-0.5 rounded bg-white/5 ${currentSentiment?.color}`}>
                    {currentSentiment?.icon}
                    {currentSentiment?.label}
                  </span>
                )}
                {tags?.split(' ').filter(t => t.startsWith('#')).map(tag => (
                  <span key={tag} className="text-[9px] font-bold text-blue-400 bg-blue-400/10 px-1.5 py-0.5 rounded border border-blue-400/20">
                    {tag}
                  </span>
                ))}
              </div>
            )}
          </div>
          
          <button
            onClick={() => setEditing(true)}
            className="text-[10px] font-bold uppercase tracking-widest text-[--text-muted] hover:text-green-400 transition-colors cursor-pointer shrink-0 py-1"
          >
            {notes ? 'Modifier' : 'Ajouter Note'}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white/[0.02] border border-white/5 rounded-xl p-4 space-y-4 animate-fade-in">
      <div className="space-y-3">
        {/* Sentiment Picker */}
        <div className="flex items-center gap-4">
          <span className="text-[10px] font-bold text-[--text-muted] uppercase">Sentiment :</span>
          <div className="flex gap-2">
            {SENTIMENTS.map(s => (
              <button
                key={s.value}
                onClick={() => setFormData({ ...formData, sentiment: s.value })}
                className={`p-2 rounded-lg border transition-all cursor-pointer ${
                  formData.sentiment === s.value 
                    ? `bg-white/10 border-white/20 ${s.color} scale-110` 
                    : 'bg-white/5 border-transparent text-[--text-muted] hover:border-white/10'
                }`}
                title={s.label}
              >
                {s.icon}
              </button>
            ))}
          </div>
        </div>

        {/* Note Text */}
        <textarea
          value={formData.notes}
          onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
          rows={2}
          className="w-full bg-[--bg-primary] border border-white/10 rounded-lg px-3 py-2 text-xs text-white focus:border-green-500/50 outline-none resize-none"
          placeholder="Pourquoi ce trade ? Qu'avez-vous appris ?"
          autoFocus
        />

        {/* Tag Selection */}
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Tag size={12} className="text-[--text-muted]" />
            <input 
              type="text"
              value={formData.tags}
              onChange={(e) => setFormData({ ...formData, tags: e.target.value })}
              className="bg-transparent border-none text-[10px] text-blue-400 w-full outline-none font-bold"
              placeholder="#Tag1 #Tag2..."
            />
          </div>
          <div className="flex flex-wrap gap-1.5">
            {PRESET_TAGS.map(tag => (
              <button
                key={tag}
                onClick={() => toggleTag(tag)}
                className={`text-[9px] px-2 py-0.5 rounded-full border transition-all cursor-pointer ${
                  formData.tags.includes(tag)
                    ? 'bg-blue-400/20 border-blue-400/40 text-blue-400'
                    : 'bg-white/5 border-transparent text-[--text-muted] hover:border-white/10'
                }`}
              >
                {tag}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="flex gap-2 pt-2">
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex-1 flex items-center justify-center gap-2 px-3 py-1.5 rounded-lg bg-green-500/10 text-green-400 border border-green-500/20 text-xs font-bold hover:bg-green-500/20 transition-all cursor-pointer"
        >
          {saving ? '...' : <Save size={14} />}
          Sauvegarder
        </button>
        <button
          onClick={handleCancel}
          className="px-3 py-1.5 rounded-lg border border-white/5 text-[--text-muted] text-xs hover:bg-white/5 transition-all cursor-pointer"
        >
          Annuler
        </button>
      </div>
    </div>
  );
}
