# Run immediately after the pinned upstream config_bd.tcl creates v80_base.
# Keep the existing CPM/NoC/SmartConnect addressing, clocks and resets.
add_files -norecurse [list [file join $flle_asset_dir market_filter_axil.sv] $flle_core_file]
update_compile_order -fileset sources_1
set old_gpio [get_bd_cells -quiet /PF1/axi_gpio_test_pf1]
if {[llength $old_gpio] != 1} { error "Expected exactly one upstream PF1 GPIO" }
delete_bd_objs $old_gpio
current_bd_instance /PF1
create_bd_cell -type module -reference market_filter_axil flle_filter
current_bd_instance /
connect_bd_intf_net [get_bd_intf_pins /PF1/smartconnect_pf1/M00_AXI] [get_bd_intf_pins /PF1/flle_filter/S_AXI]
connect_bd_net [get_bd_pins /PF1/s_axi_aclk] [get_bd_pins /PF1/flle_filter/s_axi_aclk]
connect_bd_net [get_bd_pins /PF1/s_axi_aresetn] [get_bd_pins /PF1/flle_filter/s_axi_aresetn]
set filter_seg [get_bd_addr_segs -quiet /PF1/flle_filter/S_AXI/*]
if {[llength $filter_seg] != 1} { error "Vivado must infer exactly one AXI-Lite address segment" }
# Preserve the GPIO's original five address views, including PF1 PCIe BAR2.
foreach master {CPM_PCIE_NOC_1 FPD_CCI_NOC_0 FPD_CCI_NOC_1 FPD_CCI_NOC_2 FPD_CCI_NOC_3} {
    assign_bd_address -offset 0x020200020000 -range 0x00001000 \
        -target_address_space [get_bd_addr_spaces cips/$master] $filter_seg -force
}
validate_bd_design
save_bd_design
