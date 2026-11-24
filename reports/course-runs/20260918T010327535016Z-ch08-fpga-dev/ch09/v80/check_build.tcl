# Sourced in Vivado after open_run impl_1 and before XSA export.
# These guards are implemented but have not been executed in Vivado in this lab.
set report_dir [file normalize [file join $proj_dir flle_reports]]
file mkdir $report_dir
report_timing_summary -check_timing_verbose -report_unconstrained -file [file join $report_dir timing_summary.rpt]
report_utilization -file [file join $report_dir utilization.rpt]
report_drc -file [file join $report_dir drc.rpt]
foreach delay {max min} {
    set paths [get_timing_paths -delay_type $delay -max_paths 1]
    if {[llength $paths] != 1} { error "No $delay timing path: inspect constraints" }
    if {[get_property SLACK $paths] < 0} { error "Negative $delay timing slack" }
}
set severe [get_drc_violations -quiet -filter {SEVERITY == "Error" || SEVERITY == "Critical Warning"}]
if {[llength $severe]} { error "DRC errors/critical warnings: $severe" }
set impl_dir [get_property DIRECTORY [get_runs impl_1]]
set boot [glob -nocomplain -directory $impl_dir *_boot.pdi]
set pld [glob -nocomplain -directory $impl_dir *_pld.pdi]
if {[llength $boot] != 1 || [llength $pld] != 1} {
    error "Expected exactly one Boot PDI and one PLD PDI from segmented configuration"
}
set manifest [open [file join $report_dir artifacts.txt] w]
puts $manifest "boot_pdi=[file normalize [lindex $boot 0]]"
puts $manifest "pld_pdi=[file normalize [lindex $pld 0]]"
puts $manifest "xsa=[file normalize [file join $proj_dir v80_base.xsa]]"
puts $manifest "These paths record this build; verify matching Boot/PLD before programming."
close $manifest
