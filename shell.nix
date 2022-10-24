{ pkgs ? import <nixpkgs> {} }:
(pkgs.buildFHSUserEnv {
  name = "photo-sort";
  targetPkgs = pkgs: (with pkgs; [
    zlib
  ]);
  multiPkgs = pkgs: (with pkgs; [
  ]);
  runScript = "bash ./setup.sh";
}).env
