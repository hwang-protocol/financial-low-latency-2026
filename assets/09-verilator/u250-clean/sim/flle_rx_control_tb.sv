`timescale 1ns/1ps
// Default: test real FLLE registers + filter without proprietary vendor models.
// flle_rx_port_tb below selects the actual AMD converter for Windows XSim.
module flle_rx_control_tb #(parameter integer USE_VENDOR_CDC = 0);
    localparam logic [31:0] TTL = 2048;
    logic clk = 0, axil_clk = 0;
    always #2 clk = ~clk;
    initial begin #1; forever #4 axil_clk = ~axil_clk; end
    wire bus_clk = USE_VENDOR_CDC ? axil_clk : clk;
    logic rst_n = 0;
    logic [31:0] s_awaddr = 0, s_wdata = 0, s_araddr = 0;
    logic [3:0] s_wstrb = 15;
    logic s_awvalid = 0, s_wvalid = 0, s_bready = 0, s_arvalid = 0, s_rready = 0;
    wire s_awready, s_wready, s_bvalid, s_arready, s_rvalid;
    wire [1:0] s_bresp, s_rresp;
    wire [31:0] s_rdata;
    wire cfg_valid, cfg_arm, cfg_ready;
    wire [31:0] passed_frames, dropped_frames, remaining_drops;
    wire [63:0] last_drop_sequence;
    logic s_axis_tvalid = 0, s_axis_tlast = 0;
    logic [511:0] s_axis_tdata = 0;
    logic [63:0] s_axis_tkeep = 0;
    logic [47:0] s_axis_tuser = 0;
    wire s_axis_tready, m_axis_tvalid, m_axis_tlast;
    wire [511:0] m_axis_tdata;
    wire [63:0] m_axis_tkeep;
    wire [47:0] m_axis_tuser;
    logic m_axis_tready = 1;

    generate if (USE_VENDOR_CDC == 0) begin : local_test
        flle_rx_regs #(.ARM_TIMEOUT_CYCLES(TTL)) regs (.clk(clk), .rst_n(rst_n), .*);
        flle_rx_filter #(.ARM_TIMEOUT_CYCLES(TTL)) filter_inst (.clk(clk), .rst_n(rst_n), .*);
    end else begin : vendor_test
        flle_rx_port #(.ARM_TIMEOUT_CYCLES(TTL)) port_inst (
            .axil_aclk(axil_clk), .axil_aresetn(rst_n),
            .axis_aclk(clk), .axis_aresetn(rst_n),
            .s_axil_awaddr(s_awaddr), .s_axil_awvalid(s_awvalid), .s_axil_awready(s_awready),
            .s_axil_wdata(s_wdata), .s_axil_wvalid(s_wvalid), .s_axil_wready(s_wready),
            .s_axil_bresp(s_bresp), .s_axil_bvalid(s_bvalid), .s_axil_bready(s_bready),
            .s_axil_araddr(s_araddr), .s_axil_arvalid(s_arvalid), .s_axil_arready(s_arready),
            .s_axil_rdata(s_rdata), .s_axil_rresp(s_rresp),
            .s_axil_rvalid(s_rvalid), .s_axil_rready(s_rready),
            .s_axis_tvalid(s_axis_tvalid), .s_axis_tready(s_axis_tready),
            .s_axis_tdata(s_axis_tdata), .s_axis_tkeep(s_axis_tkeep),
            .s_axis_tlast(s_axis_tlast), .s_axis_tuser(s_axis_tuser),
            .m_axis_tvalid(m_axis_tvalid), .m_axis_tready(m_axis_tready),
            .m_axis_tdata(m_axis_tdata), .m_axis_tkeep(m_axis_tkeep),
            .m_axis_tlast(m_axis_tlast), .m_axis_tuser(m_axis_tuser)
        );
    end endgenerate

    integer cases = 0, wr = 0, rd = 0;
    logic [624:0] expected [0:255];
    logic [624:0] held;
    bit stalled = 0;
    byte unsigned frame[0:127];
    logic [31:0] value;
    always @(posedge clk) begin
        if (!rst_n) stalled = 0;
        else begin
            if (stalled && (!m_axis_tvalid ||
                {m_axis_tdata,m_axis_tkeep,m_axis_tlast,m_axis_tuser} !== held))
                $fatal(1,"packet output changed under backpressure");
            if (m_axis_tvalid && m_axis_tready) begin
                if (rd >= wr || {m_axis_tdata,m_axis_tkeep,m_axis_tlast,m_axis_tuser} !== expected[rd])
                    $fatal(1,"packet mismatch or unexpected beat at %0d",rd);
                rd = rd+1;
            end
            stalled = m_axis_tvalid && !m_axis_tready;
            held = {m_axis_tdata,m_axis_tkeep,m_axis_tlast,m_axis_tuser};
        end
    end
    task automatic passed(input string label_text);
        cases = cases+1; $display("CONTROL_CASE_PASS %0d %s", cases, label_text);
    endtask
    task automatic send_aw(input logic [31:0] address);
        @(negedge bus_clk); s_awaddr = address; s_awvalid = 1;
        do @(posedge bus_clk); while (!s_awready);
        @(negedge bus_clk); s_awvalid = 0;
    endtask
    task automatic send_w(input logic [31:0] data);
        @(negedge bus_clk); s_wdata = data; s_wvalid = 1;
        do @(posedge bus_clk); while (!s_wready);
        @(negedge bus_clk); s_wvalid = 0;
    endtask
    task automatic get_b(input logic [1:0] response);
        wait(s_bvalid);
        repeat (4) begin
            @(negedge bus_clk);
            if (!s_bvalid || s_bresp !== response) $fatal(1,"write response unstable/wrong");
        end
        s_bready = 1;
        @(negedge bus_clk); s_bready = 0;
    endtask
    task automatic write_reg(input logic [31:0] address, data,
                             input bit data_first, input logic [1:0] response);
        if (data_first) begin send_w(data); repeat(3) @(negedge bus_clk); send_aw(address); end
        else begin send_aw(address); repeat(3) @(negedge bus_clk); send_w(data); end
        get_b(response);
    endtask
    task automatic read_reg(input logic [31:0] address, input logic [1:0] response,
                            output logic [31:0] data);
        @(negedge bus_clk); s_araddr = address; s_arvalid = 1;
        do @(posedge bus_clk); while (!s_arready);
        @(negedge bus_clk); s_arvalid = 0;
        wait(s_rvalid); data = s_rdata;
        repeat(4) begin
            @(negedge bus_clk);
            if (!s_rvalid || s_rdata !== data || s_rresp !== response)
                $fatal(1,"read response unstable/wrong");
        end
        s_rready = 1;
        @(negedge bus_clk); s_rready = 0;
    endtask
    task automatic expect_reg(input logic [31:0] address, data);
        logic [31:0] actual;
        read_reg(address, 0, actual);
        if (actual !== data) $fatal(1,"register %h got %h expected %h",address,actual,data);
    endtask
    task automatic make_frame(input logic [63:0] seq, input bit target);
        integer sum, c;
        for(integer j=0;j<128;j=j+1) frame[j]=0;
        frame[12]=8'h08; frame[14]=8'h45; frame[17]=86; frame[22]=64; frame[23]=17;
        frame[26]=20; frame[27]=1; frame[28]=1; frame[29]=1;
        frame[30]=233; frame[31]=74; frame[32]=125; frame[33]=32;
        frame[36]=8'h79; frame[37]=8'h38; frame[39]=66;
        // IPv4 UDP checksum zero is permitted. Compute IPv4 checksum independently.
        sum=0;
        for(integer j=14;j<34;j=j+2) sum=sum+(int'(frame[j])<<8)+int'(frame[j+1]);
        sum=(sum & 65535)+(sum>>16); c=(~sum)&65535;
        frame[24]=8'(c>>8); frame[25]=8'(c);
        for(integer j=0;j<8;j=j+1) frame[52+j]=seq[63-8*j-:8];
        frame[61]=1; frame[63]=36; frame[64]=target ? "A" : "F";
        frame[65]=8'h1f; frame[66]=8'h9f;
        frame[88]="N"; frame[89]="V"; frame[90]="D"; frame[91]="A";
        frame[92]=" "; frame[93]=" "; frame[94]=" "; frame[95]=" ";
    endtask
    task automatic send_beat(input integer base, input bit should_drop);
        logic [511:0] data;
        logic [63:0] keep;
        logic [47:0] user_bits;
        data=0; keep=0; user_bits={16'h1,16'h40,16'd100};
        for(integer j=0;j<64;j=j+1) if(base+j<100) begin
            data[j*8+:8]=frame[base+j]; keep[j]=1;
        end
        if(!should_drop) begin expected[wr]={data,keep,(base==64),user_bits}; wr=wr+1; end
        @(negedge clk);
        s_axis_tdata=data; s_axis_tkeep=keep; s_axis_tuser=user_bits;
        s_axis_tlast=(base==64); s_axis_tvalid=1;
        do @(posedge clk); while(!s_axis_tready);
        @(negedge clk); s_axis_tvalid=0;
    endtask
    task automatic packet(input logic [63:0] seq, input bit target, should_drop);
        make_frame(seq,target); send_beat(0,should_drop); send_beat(64,should_drop);
        // Bounded settling time includes the adapter's checksum pipeline.
        // This is simulation time, not a throughput or latency requirement.
        repeat(32) @(negedge clk);
        if(m_axis_tready && rd!=wr) $fatal(1,"output packet did not drain");
    endtask
    initial begin
        repeat(40) @(negedge bus_clk); rst_n=1;
        repeat(40) @(negedge bus_clk);
        expect_reg(0,32'h464c4c45); expect_reg(4,32'h00010000);
        expect_reg(16,0); expect_reg(36,TTL);
        packet(1,1,0); expect_reg(20,1); passed("reset_default_pass_and_registers");
        write_reg(8,1,0,0); expect_reg(16,1);
        packet(64'h123456789abcdef0,1,1); expect_reg(24,1); expect_reg(16,0);
        expect_reg(28,32'h9abcdef0); passed("address_before_data_arm_and_drop_once");
        write_reg(8,1,1,0); packet(64'h8765432101234567,1,1);
        expect_reg(32,32'h12345678); // high half held by prior low-half read
        expect_reg(28,32'h01234567); expect_reg(32,32'h87654321);
        passed("data_before_address_and_coherent_sequence_read");
        packet(3,1,0); expect_reg(20,2); passed("next_target_passes");
        write_reg(8,1,0,0); packet(4,0,0); expect_reg(16,1);
        write_reg(8,0,1,0); packet(5,1,0); expect_reg(16,0);
        passed("non_target_preserves_credit_and_disarm");
        write_reg(8,2,0,2); write_reg(0,1,1,2); write_reg(32'h88,1,0,2);
        read_reg(32'h80,2,value); read_reg(1,2,value); expect_reg(16,0);
        passed("invalid_data_address_and_alignment_rejected");
        fork
            send_aw(8);
            send_w(0);
        join
        get_b(0); expect_reg(16,0); passed("simultaneous_address_and_data");
        if(USE_VENDOR_CDC==0) begin
            s_wstrb=1; write_reg(8,1,0,2); s_wstrb=15;
            expect_reg(16,0); passed("partial_command_rejected");
        end
        write_reg(8,1,0,0);
        repeat(2100) @(negedge clk);
        expect_reg(16,0); packet(6,1,0); passed("unused_credit_expires");
        // Hold the second beat beyond expiry: this must not result in a late drop.
        write_reg(8,1,1,0); make_frame(7,1); send_beat(0,0);
        repeat(2100) @(negedge clk);
        send_beat(64,0); repeat(20) @(negedge clk);
        expect_reg(16,0); expect_reg(24,2); passed("expiry_during_partial_packet");
        // A write can be buffered while output is stalled; B must await application.
        m_axis_tready=0; packet(8,0,0);
        fork
            begin write_reg(8,1,0,0); end
            begin
                repeat(100) @(negedge bus_clk);
                if(s_bvalid) $fatal(1,"command acknowledged inside stalled frame");
                m_axis_tready=1;
            end
        join
        packet(9,1,1); expect_reg(24,3); passed("command_waits_for_frame_boundary");
        // Reset after AW only: the abandoned address must never arm the filter.
        send_aw(8); @(negedge bus_clk); rst_n=0;
        repeat(40) @(negedge bus_clk); rst_n=1;
        repeat(40) @(negedge bus_clk);
        expect_reg(16,0); expect_reg(20,0); expect_reg(24,0);
        write_reg(8,0,1,0); packet(10,1,0);
        passed("reset_aborts_partial_write_and_clears_state");
        if(rd!=wr) $fatal(1,"scoreboard not drained");
        $display("U250_RX_CONTROL_SIMULATION=PASS cases=%0d vendor_cdc=%0d hardware=NOT_RUN",cases,USE_VENDOR_CDC);
        $finish;
    end
    initial begin #200000; $fatal(1,"control test timeout"); end
endmodule

// Select THIS top in the real OpenNIC Vivado project to include AMD IP models.
module flle_rx_port_tb;
    flle_rx_control_tb #(.USE_VENDOR_CDC(1)) test_inst();
endmodule
