import { Icon } from "@chakra-ui/react";

export function EditRecipeIcon() {
  return (
    <Icon viewBox="0 0 24 24" boxSize={5}>
      <path
        fill="currentColor"
        d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zm17.71-10.04a.996.996 0 0 0 0-1.41l-2.5-2.5a.996.996 0 0 0-1.41 0l-1.96 1.96 3.75 3.75 1.92-1.8z"
      />
    </Icon>
  );
}

export function DeleteRecipeIcon() {
  return (
    <Icon viewBox="0 0 24 24" boxSize={5}>
      <path
        fill="currentColor"
        d="M9 3h6l1 2h5v2H3V5h5l1-2zm1 6h2v9h-2V9zm4 0h2v9h-2V9zM7 9h2v9H7V9zm-1 12c-1.1 0-2-.9-2-2V8h16v11c0 1.1-.9 2-2 2H6z"
      />
    </Icon>
  );
}

export function PencilIcon() {
  return (
    <Icon viewBox="0 0 24 24" boxSize={4}>
      <path
        fill="currentColor"
        d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25Zm17.71-10.04a.996.996 0 0 0 0-1.41l-2.5-2.5a.996.996 0 0 0-1.41 0l-1.96 1.96 3.75 3.75 1.92-1.8Z"
      />
    </Icon>
  );
}

export function SearchGlyph() {
  return (
    <svg
      aria-hidden="true"
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-3.5-3.5" />
    </svg>
  );
}

export function FilterSortIcon() {
  return (
    <svg
      aria-hidden="true"
      width="14"
      height="14"
      viewBox="0 0 20 20"
      fill="none"
    >
      <path
        d="M3 5h14M6 10h8M8.5 15h3"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.8"
      />
    </svg>
  );
}

export function BowlDoodle({ size = 56 }: { size?: number }) {
  return (
    <svg
      aria-hidden="true"
      width={size}
      height={size}
      viewBox="0 0 64 64"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M10 32h44a22 22 0 0 1-44 0Z" />
      <path d="M22 32c1-7 4-12 10-15M36 30c0-5 3-9 8-11" />
      <path d="M26 54h12M30 54v4M34 54v4" />
    </svg>
  );
}
