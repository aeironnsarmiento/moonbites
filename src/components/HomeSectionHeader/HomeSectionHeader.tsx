import "./HomeSectionHeader.scss";

type HomeSectionHeaderProps = {
  eyebrow: string;
  title: string;
  count?: number;
  action?: string;
  onAction?: () => void;
};

export function HomeSectionHeader({
  eyebrow,
  title,
  count,
  action,
  onAction,
}: HomeSectionHeaderProps) {
  return (
    <div className="homeSectionHeader">
      <div>
        <div className="homeSectionHeader__eyebrow">{eyebrow}</div>
        <h2 className="homeSectionHeader__title">
          {title}
          {typeof count === "number" && (
            <span className="homeSectionHeader__count">{count}</span>
          )}
        </h2>
      </div>
      {action && onAction && (
        <button onClick={onAction} className="homeSectionHeader__action">
          {action} →
        </button>
      )}
    </div>
  );
}
