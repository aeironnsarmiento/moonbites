import { extendTheme } from "@chakra-ui/react";

export const chakraTheme = extendTheme({
  fonts: {
    heading: "Inter, system-ui, sans-serif",
    body: "Inter, system-ui, sans-serif",
  },
  colors: {
    brand: {
      50: "#fbfcf8",
      100: "#f0f4e3",
      200: "#e3ebcf",
      300: "#d2deb0",
      400: "#b8ca89",
      500: "#9cb160",
      600: "#7c9446",
      700: "#627537",
      800: "#4d5b2d",
      900: "#3e4926",
    },
  },
  styles: {
    global: {
      body: {
        bg: "#f5f7fb",
        color: "#1f2937",
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
          borderRadius: "24px",
          borderWidth: "1px",
          borderColor: "blackAlpha.100",
          boxShadow: "0 20px 50px rgba(15, 23, 42, 0.08)",
        },
      },
    },
  },
});
