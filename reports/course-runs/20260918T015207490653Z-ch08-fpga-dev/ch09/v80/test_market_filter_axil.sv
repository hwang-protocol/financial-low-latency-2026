`timescale 1ns/1ps
module test_market_filter_axil;
    logic clk=0, rst_n=0;
    always #5 clk=~clk;
    logic [11:0] awaddr=0, araddr=0;
    logic [31:0] wdata=0, rdata;
    logic [3:0] wstrb=0;
    logic awvalid=0, awready, wvalid=0, wready, bvalid, bready=0;
    logic arvalid=0, arready, rvalid, rready=0;
    logic [1:0] bresp, rresp;
    int checks=0;
    market_filter_axil dut (
        .s_axi_aclk(clk), .s_axi_aresetn(rst_n),
        .s_axi_awaddr(awaddr), .s_axi_awprot(3'd0), .s_axi_awvalid(awvalid), .s_axi_awready(awready),
        .s_axi_wdata(wdata), .s_axi_wstrb(wstrb), .s_axi_wvalid(wvalid), .s_axi_wready(wready),
        .s_axi_bresp(bresp), .s_axi_bvalid(bvalid), .s_axi_bready(bready),
        .s_axi_araddr(araddr), .s_axi_arprot(3'd0), .s_axi_arvalid(arvalid), .s_axi_arready(arready),
        .s_axi_rdata(rdata), .s_axi_rresp(rresp), .s_axi_rvalid(rvalid), .s_axi_rready(rready)
    );
    task automatic send_aw(input [11:0] a);
        @(negedge clk); awaddr=a; awvalid=1;
        do @(posedge clk); while (!awready);
        @(negedge clk); awvalid=0;
    endtask
    task automatic send_w(input [31:0] d, input [3:0] strb);
        @(negedge clk); wdata=d; wstrb=strb; wvalid=1;
        do @(posedge clk); while (!wready);
        @(negedge clk); wvalid=0;
    endtask
    task automatic wr(input [11:0] a, input [31:0] d,
                      input [3:0] strb=15, input int order=0,
                      input int stall=0, input [1:0] response=0);
        case (order)
            0: fork send_aw(a); send_w(d,strb); join
            1: begin send_aw(a); repeat(3) @(negedge clk); send_w(d,strb); end
            2: begin send_w(d,strb); repeat(3) @(negedge clk); send_aw(a); end
        endcase
        while (!bvalid) @(negedge clk);
        repeat(stall+1) begin
            if (!bvalid || bresp!==response || awready || wready)
                $fatal(1,"write response unstable/mismatched at %h",a);
            @(negedge clk);
        end
        bready=1; @(negedge clk); bready=0;
        checks++;
    endtask
    task automatic rd(input [11:0] a, input [31:0] expected,
                      input int stall=0, input [1:0] response=0);
        @(negedge clk); araddr=a; arvalid=1;
        do @(posedge clk); while (!arready);
        @(negedge clk); arvalid=0;
        while (!rvalid) @(negedge clk);
        repeat(stall+1) begin
            if (!rvalid || rresp!==response || rdata!==expected || arready)
                $fatal(1,"read %h expected %h/%h got %h/%h",a,expected,response,rdata,rresp);
            @(negedge clk);
        end
        rready=1; @(negedge clk); rready=0;
        checks++;
    endtask
    task automatic reset_core;
        @(negedge clk); rst_n=0;
        repeat(3) @(negedge clk);
        rst_n=1; repeat(2) @(negedge clk);
    endtask
    task automatic packet(input [63:0] seq, input bit dropped,
                          input [31:0] passes, drops, quota);
        wr(12'h030,seq[31:0]); wr(12'h034,seq[63:32]);
        wr(12'h004,2,15,0,6); // Holding BREADY low must not repeat the command.
        rd(12'h008,dropped ? 6 : 2,3);
        rd(12'h018,seq[31:0]); rd(12'h01c,seq[63:32]);
        rd(12'h010,passes); rd(12'h014,drops); rd(12'h00c,quota);
    endtask
    initial begin
        reset_core();
        rd(0,32'h464c4c39,4); rd(12'h008,0); rd(12'h00c,0);
        wr(12'h030,32'h11223344,15,1,4);
        wr(12'h030,32'haabbccdd,5,2,3);
        rd(12'h030,32'h11bb33dd,4);
        wr(12'h030,32'hffffffff,0); rd(12'h030,32'h11bb33dd);
        wr(12'h020,32'h0000ffff,1); rd(12'h020,32'h00001fff);
        wr(12'h020,8095);
        wr(12'h000,0,15,0,0,2); // APP_ID is read only.
        wr(12'h031,0,15,0,0,2); // Misalignment is rejected.
        wr(12'h080,0,15,0,0,2); rd(12'h080,0,0,2);
        rd(12'h031,0,0,2);
        wr(12'h004,1,0); rd(12'h00c,0);
        wr(12'h004,1,2); rd(12'h00c,0); // No low-byte strobe, no arm.
        wr(12'h004,3,15,0,0,2); rd(12'h00c,0);
        for (int i=0;i<9;i++) wr(12'(12'h040+i*4),0);
        wr(12'h040,32'h411f9f00,15,1);
        wr(12'h058,32'h4e564441,15,2);
        wr(12'h05c,32'h20202020);
        packet(646,0,1,0,0);
        wr(12'h004,1); rd(12'h00c,1);
        packet(647,1,1,1,0);
        packet(648,0,2,1,0);
        wr(12'h004,1); wr(12'h058,32'h4d534654); // MSFT misses and preserves quota.
        packet(64'h1234567800000649,0,3,1,1);
        wr(12'h058,32'h4e564441);
        packet(64'h1234567800000650,1,3,2,0);
        wr(12'h004,1); wr(12'h004,4); rd(12'h00c,0);
        packet(651,0,4,2,0);
        // Reset discards an address without its data; no unintended arm.
        send_aw(12'h004); reset_core();
        send_w(1,15); repeat(4) @(negedge clk);
        if (bvalid) $fatal(1,"reset retained stale AW");
        rd(12'h00c,0); reset_core();
        // Also discard data without its address on reset.
        send_w(1,15); reset_core(); send_aw(12'h004);
        repeat(4) @(negedge clk);
        if (bvalid) $fatal(1,"reset retained stale W");
        rd(12'h00c,0); reset_core();
        rd(12'h010,0); rd(12'h014,0); rd(12'h008,0);
        // Independent review: read response must remain latched while writes change the register.
        @(negedge clk); araddr=12'h00c; arvalid=1;
        do @(posedge clk); while (!arready);
        @(negedge clk); arvalid=0;
        while (!rvalid) @(negedge clk);
        if (rdata!==0 || rresp!==0) $fatal(1,"initial held read failed");
        wr(12'h004,1,15,1,5);
        repeat(10) @(negedge clk);
        if (!rvalid || rdata!==0 || rresp!==0 || arready)
            $fatal(1,"R payload changed while stalled across a register write");
        rready=1; @(negedge clk); rready=0;
        rd(12'h00c,1);
        // Held BVALID must not re-submit; AR reads can progress independently.
        // Reset left the message all-zero, so one submit must increment PASS exactly once.
        wr(12'h030,32'h12345678);
        fork send_aw(12'h004); send_w(2,15); join
        while (!bvalid) @(negedge clk);
        repeat(12) @(negedge clk);
        rd(12'h010,1,4);
        rd(12'h014,0);
        rd(12'h018,32'h12345678);
        rd(12'h008,2);
        if (!bvalid || bresp!==0 || awready || wready)
            $fatal(1,"B response changed while independent reads progressed");
        repeat(20) @(negedge clk);
        rd(12'h010,1);
        bready=1; @(negedge clk); bready=0;
        repeat(10) @(negedge clk);
        rd(12'h010,1);
        $display("INDEPENDENT_CHECK_PASS held_read_across_write=1 held_submit_exactly_once=1 independent_read_write_channels=1");
        $display("PASS: %0d AXI-Lite register/response checks; independent AW/W, WSTRB, backpressure, reset, same-RTL pass/drop/sequence",checks);
        $finish;
    end
    initial begin #200000; $fatal(1,"timeout"); end
endmodule
