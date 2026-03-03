import { useState } from 'react';

export default function NoteEditor({ notes, source, id, onSaved }) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(notes || '');
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    try {
      const { api } = await import('../../api/client');
      if (source === 'paper') {
        await api.journalPaperNote(id, text);
      } else {
        await api.journalLiveNote(id, text);
      }
      setEditing(false);
      onSaved?.();
    } catch (err) {
      console.error('Failed to save note:', err);
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    setText(notes || '');
    setEditing(false);
  };

  if (!editing) {
    return (
      <div className="flex items-start gap-2 min-h-[24px]">
        {notes ? (
          <span className="text-xs text-[--text-secondary] italic flex-1">{notes}</span>
        ) : (
          <span className="text-xs text-[--text-muted] flex-1">No notes</span>
        )}
        <button
          onClick={() => setEditing(true)}
          className="text-xs text-[--text-muted] hover:text-[--text-secondary] transition-colors cursor-pointer shrink-0"
        >
          {notes ? 'Edit' : 'Add note'}
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={2}
        className="w-full bg-[--bg-primary] border border-[--border-subtle] rounded px-3 py-1.5 text-xs text-[--text-primary] focus:border-blue-500/50 focus:outline-none resize-none"
        placeholder="Add a note about this trade..."
        autoFocus
      />
      <div className="flex gap-2">
        <button
          onClick={handleSave}
          disabled={saving}
          className="px-3 py-1 rounded text-xs bg-blue-600 text-white hover:bg-blue-500 disabled:opacity-50 cursor-pointer transition-colors"
        >
          {saving ? 'Saving...' : 'Save'}
        </button>
        <button
          onClick={handleCancel}
          className="px-3 py-1 rounded text-xs border border-[--border-subtle] text-[--text-secondary] hover:bg-white/5 cursor-pointer transition-colors"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
