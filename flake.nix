{
  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    flake-parts.url = "github:hercules-ci/flake-parts";

    pyproject-nix = {
      url = "github:pyproject-nix/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    uv2nix = {
      url = "github:pyproject-nix/uv2nix";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    pyproject-build-systems = {
      url = "github:pyproject-nix/build-system-pkgs";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.uv2nix.follows = "uv2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    inputs@{ flake-parts, ... }:
    flake-parts.lib.mkFlake { inherit inputs; } {
      systems = [
        "aarch64-darwin"
        "x86_64-linux"
        "aarch64-linux"
      ];
      debug = true;
      perSystem =
        {
          lib,
          pkgs,
          ...
        }:
        let
          inherit (pkgs.callPackages inputs.pyproject-nix.build.util { }) mkApplication;

          workspace = inputs.uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ./.; };

          overlay = workspace.mkPyprojectOverlay {
            sourcePreference = "wheel";
          };

          editableOverlay = workspace.mkEditablePyprojectOverlay {
            root = "$REPO_ROOT";
          };

          pythonSet =
            (pkgs.callPackage inputs.pyproject-nix.build.packages {
              python = pkgs.python3;
            }).overrideScope
              (
                lib.composeManyExtensions [
                  inputs.pyproject-build-systems.overlays.wheel
                  overlay
                ]
              );

        in
        {
          devShells =
            let
              pythonSet' = pythonSet.overrideScope editableOverlay;
              virtualenv = pythonSet'.mkVirtualEnv "ics-to-wiki-dev-env" workspace.deps.all;
            in
            {
              default = pkgs.mkShell {
                packages = [
                  virtualenv
                  pkgs.uv
                  pythonSet'.ics-to-wiki
                ];
                env = {
                  UV_NO_SYNC = "1";
                  UV_PYTHON = pythonSet'.python.interpreter;
                  UV_PYTHON_DOWNLOADS = "never";
                };
                shellHook = ''
                  unset PYTHONPATH
                  export REPO_ROOT=$(git rev-parse --show-toplevel)
                '';
              };
            };

          packages =
            let
              venv = pythonSet.mkVirtualEnv "ics-to-wiki-env" workspace.deps.default;
            in
            {
              default = mkApplication {
                inherit venv;
                package = pythonSet.ics-to-wiki;
              };

              sbom = pkgs.runCommandNoCC "build-sbom" { nativeBuildInputs = [ pkgs.cyclonedx-python ]; } ''
                cyclonedx-py environment ${venv} --output-reproducible --outfile $out
              '';
            };
        };
    };
}
