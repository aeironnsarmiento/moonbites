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

export function HeaderBar() {
  const isScrolled = useScrolled();
  const { isAdmin } = useAuth();
  const visibleNavItems = navItems.filter(
    (item) => item.to !== "/recipes/create" || isAdmin,
  );

  return (
    <motion.header
      animate={{
        backgroundColor: isScrolled ? "#99a293" : "#ccd1c3",
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
            <Text as="span" className="headerBar__brandPrimary">
              Moonbites
            </Text>
            <Text as="span" className="headerBar__brandEyebrow">
              Cookbook
            </Text>
          </Box>
        </Box>

        <HStack spacing={2} className="headerBar__nav">
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
