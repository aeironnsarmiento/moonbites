import { extendTheme } from "@chakra-ui/react";

export const chakraTheme = extendTheme({
  fonts: {
    heading: "Inter, system-ui, sans-serif",
    body: "Inter, system-ui, sans-serif",
  },
  colors: {
    brand: {
      50: "#f8faf3",
      100: "#edf1e2",
      200: "#dce4c9",
      300: "#c3d0a8",
      400: "#9eae77",
      500: "#68784A",
      600: "#59683f",
      700: "#495536",
      800: "#39432c",
      900: "#2d3524",
    },
    surface: {
      page: "#f0f4e2",
      header: "#ccd1c3",
      headerScrolled: "#99a293",
      card: "#ccd1c3",
    },
  },
  styles: {
    global: {
      body: {
        bg: "surface.page",
        color: "gray.800",
      },
    },
  },
  components: {
    Button: {
      defaultProps: {
        colorScheme: "brand",
      },
    },
    Card: {
      baseStyle: {
        container: {
          bg: "surface.card",
          borderRadius: "24px",
          borderWidth: "1px",
          borderColor: "blackAlpha.100",
          boxShadow: "0 8px 24px rgba(74, 87, 60, 0.12)",
        },
      },
    },
  },
});
