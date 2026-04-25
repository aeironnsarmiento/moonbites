import { Box, Button, Flex, HStack, Image, Text } from "@chakra-ui/react";
import { motion } from "framer-motion";
import { NavLink, Link } from "react-router-dom";

import { useScrolled } from "../../hooks/useScrolled";
import "./HeaderBar.scss";

const navItems = [
  { label: "Recipe List", to: "/recipes" },
  { label: "Create Recipe", to: "/recipes/create" },
];

export function HeaderBar() {
  const isScrolled = useScrolled();

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
            <Text as="span">Moonbites</Text>
            <Text as="span">Cookbook</Text>
          </Box>
        </Box>

        <HStack spacing={3}>
          {navItems.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.to === "/"}>
              {({ isActive }) => (
                <Button
                  variant={isActive ? "solid" : "ghost"}
                  className="headerBar__navButton"
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
