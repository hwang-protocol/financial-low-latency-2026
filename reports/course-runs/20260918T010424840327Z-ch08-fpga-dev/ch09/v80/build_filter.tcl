# Usage: vivado -mode batch -source build_filter.tcl -tclargs HW_REPO FRESH_BUILD_DIR
# Not executed in Vivado yet. This script fails instead of silently accepting drift.
if {$argc != 2} { error "Expected HW_REPO and FRESH_BUILD_DIR" }
if {[version -short] ne "2026.1"} { error "This integration targets Vivado 2026.1" }
set hw_root [file normalize [lindex $argv 0]]
set build_dir [file normalize [lindex $argv 1]]
set pinned 4b7d244758c683ec4c45f357e65511c25cff8f38
if {[string trim [exec git -C $hw_root rev-parse HEAD]] ne $pinned} {
    error "Use amr_vivado_designs commit $pinned"
}
exec git -C $hw_root diff --exit-code HEAD -- alveo_v80/platforms/v80_base
if {[file exists $build_dir]} { error "Use a new build directory: $build_dir" }
set flle_asset_dir [file normalize [file dirname [info script]]]
set flle_core_file [file normalize [file join $flle_asset_dir .. market_filter.sv]]
if {![file exists $flle_core_file]} { error "Missing unchanged Chapter 09 market_filter.sv" }
file mkdir $build_dir
set base_src [file join $hw_root alveo_v80 platforms v80_base]
# Copy only source inputs, never a previous project/ or .Xil build directory.
foreach item {scripts xdc ip Makefile} {
    file copy [file join $base_src $item] [file join $build_dir $item]
}
cd $build_dir
set fd [open scripts/main.tcl r]
set upstream [read $fd]
close $fd
set hook {source $bd_tcl_dir/config_bd.tcl}
if {[regexp -all -line {^source \$bd_tcl_dir/config_bd.tcl$} $upstream] != 1} {
    error "Upstream main.tcl changed: cannot install integration hook"
}
set replacement "$hook\nsource \[file join \$flle_asset_dir integrate_filter.tcl\]"
set argc 0
set argv {}
# The upstream script still controls constraints, part, project and write_device_image.
# Its XSA/PDI are outputs to validate in Vivado, not locally verified artifacts.
set check_hook {open_run impl_1}
if {[regexp -all -line {^open_run impl_1$} $upstream] != 1} {
    error "Upstream implementation hook changed"
}
set check_replacement "$check_hook\nsource \[file join \$flle_asset_dir check_build.tcl\]"
eval [string map [list $hook $replacement $check_hook $check_replacement] $upstream]
