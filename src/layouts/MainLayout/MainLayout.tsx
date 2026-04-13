import { Box, Container } from "@chakra-ui/react";
import { Outlet } from "react-router-dom";

import { HeaderBar } from "../../components/HeaderBar/HeaderBar";
import "./MainLayout.scss";

export function MainLayout() {
  return (
    <Box className="mainLayout">
      <HeaderBar />
      <Container maxW="7xl" as="main" className="mainLayout__content">
        <Outlet />
      </Container>
    </Box>
  );
}
