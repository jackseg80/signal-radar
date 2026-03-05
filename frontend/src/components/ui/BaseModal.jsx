import React, { useEffect } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';

/**
 * BaseModal component that provides a consistent structure for all modals.
 * Includes Portal, Backdrop blur, slide-up animation, and Escape key handling.
 */
export default function BaseModal({ 
  children, 
  onClose, 
  title, 
  subtitle, 
  icon: Icon,
  maxWidth = 'max-w-6xl',
  showClose = true
}) {
  useEffect(() => {
    const handler = (e) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', handler);
    document.body.style.overflow = 'hidden';
    
    return () => {
      window.removeEventListener('keydown', handler);
      document.body.style.overflow = 'unset';
    };
  }, [onClose]);

  const handleBackdropClick = (e) => {
    if (e.target === e.currentTarget) onClose();
  };

  return createPortal(
    <div 
      className="fixed inset-0 z-[1000] flex items-center justify-center bg-black/90 backdrop-blur-md p-4 sm:p-6 animate-fade-in"
      onClick={handleBackdropClick}
    >
      <div className={`bg-[#0f111a] border border-white/10 w-full ${maxWidth} max-h-[95vh] rounded-[2rem] shadow-2xl flex flex-col relative overflow-hidden animate-slide-up pointer-events-auto`}>
        
        {/* Header (Optional) */}
        {(title || showClose) && (
          <div className="relative p-6 sm:p-8 bg-gradient-to-b from-white/[0.03] to-transparent border-b border-white/5 shrink-0">
            <div className="flex items-center justify-between gap-6">
              <div className="flex items-center gap-5">
                {Icon && <div className="p-3 bg-white/5 rounded-2xl text-blue-400 shadow-xl ring-1 ring-white/10"><Icon size={24} /></div>}
                <div>
                  {title && <h2 className="text-2xl sm:text-3xl font-black text-white tracking-tight">{title}</h2>}
                  {subtitle && <p className="text-xs sm:text-sm text-[--text-muted] font-medium uppercase tracking-wider mt-1">{subtitle}</p>}
                </div>
              </div>

              {showClose && (
                <button 
                  onClick={onClose}
                  className="p-3 bg-white/5 hover:bg-white/10 rounded-2xl text-white transition-all cursor-pointer border border-white/5 shadow-lg group"
                >
                  <X size={24} className="group-hover:scale-110 transition-transform" />
                </button>
              )}
            </div>
          </div>
        )}

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto custom-scrollbar">
          {children}
        </div>
      </div>
    </div>,
    document.body
  );
}
