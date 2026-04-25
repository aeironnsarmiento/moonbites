import { useEffect, useState } from "react";

export function useScrolled(threshold = 8) {
  const [isScrolled, setIsScrolled] = useState(() => window.scrollY > threshold);

  useEffect(() => {
    let frameId = 0;

    const update = () => {
      frameId = 0;
      setIsScrolled(window.scrollY > threshold);
    };

    const handleScroll = () => {
      if (frameId === 0) {
        frameId = window.requestAnimationFrame(update);
      }
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    update();

    return () => {
      window.removeEventListener("scroll", handleScroll);
      if (frameId !== 0) {
        window.cancelAnimationFrame(frameId);
      }
    };
  }, [threshold]);

  return isScrolled;
}
