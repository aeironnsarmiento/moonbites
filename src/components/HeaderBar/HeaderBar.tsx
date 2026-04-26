import { Box, Button, Flex, HStack, Image, Text } from "@chakra-ui/react";
import { motion } from "framer-motion";
import { NavLink, Link } from "react-router-dom";

import { useAuth } from "../../hooks/useAuth";
import { useScrolled } from "../../hooks/useScrolled";
import "./HeaderBar.scss";

const navItems = [
  { label: "Recipe List", to: "/recipes", end: true },
  { label: "Create Recipe", to: "/recipes/create", end: true },
];

const subtleHeaderBackgroundImage =
  "var(--app-subtle-header-background-image, " +
  "radial-gradient(1100px 420px at 50% -160px, rgba(104, 120, 74, 0.2), rgba(104, 120, 74, 0.08) 42%, transparent 72%), " +
  "radial-gradient(circle, rgba(73, 85, 54, 0.1) 1px, transparent 1.2px))";

export function HeaderBar() {
  const isScrolled = useScrolled();
  const { isAdmin } = useAuth();
  const visibleNavItems = navItems.filter(
    (item) => item.to !== "/recipes/create" || isAdmin,
  );

  return (
    <motion.header
      style={{
        backgroundColor: isScrolled
          ? "var(--chakra-colors-surface-headerScrolled, #99a293)"
          : "var(--chakra-colors-surface-page, #f0f4e2)",
        backgroundImage: subtleHeaderBackgroundImage,
        backgroundSize: "auto, 22px 22px",
        backgroundPosition: "0 0, 0 0",
        backgroundAttachment: "fixed",
        backgroundRepeat: "no-repeat, repeat",
      }}
      animate={{
        boxShadow: isScrolled
          ? "0 4px 16px rgba(0, 0, 0, 0.08)"
          : "0 0 0 rgba(0, 0, 0, 0)",
      }}
      transition={{ duration: 0.25, ease: "easeOut" }}
      className="headerBar"
    >
      <Flex align="center" justify="space-between" className="headerBar__inner">
        <Box as={Link} to="/" className="headerBar__brand">
          <Image src="/favicon.png" alt="" className="headerBar__brandIcon" />
          <Box className="headerBar__brandText">
            <Text as="span">Moonbites</Text>
            <Text as="span">Cookbook</Text>
          </Box>
        </Box>

        <HStack spacing={3}>
          {visibleNavItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className="headerBar__navLink"
            >
              {({ isActive }) => (
                <Button
                  variant={isActive ? "solid" : "ghost"}
                  colorScheme="brand"
                  className={
                    isActive
                      ? "headerBar__navButton headerBar__navButton--active"
                      : "headerBar__navButton"
                  }
                >
                  {item.label}
                </Button>
              )}
            </NavLink>
          ))}
        </HStack>
      </Flex>
    </motion.header>
  );
}
