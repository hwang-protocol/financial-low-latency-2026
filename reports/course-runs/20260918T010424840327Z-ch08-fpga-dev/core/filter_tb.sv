`timescale 1ns/1ps
module filter_tb;
    logic clk=0, rst=1;
    always #5 clk=~clk;
    logic [63:0] s_data=0, m_data;
    logic [7:0] s_keep=0, m_keep;
    logic s_valid=0, s_last=0, s_error=0, s_ready;
    logic m_valid, m_last, m_ready=1, arm, disarm, armed;
    logic wr_en=0;
    logic [3:0] wr_addr=0, rd_addr=0;
    logic [31:0] wr_data=0, rd_data;
    logic [31:0] rx_count, tx_count, drop_count, error_count;
    logic [63:0] last_sequence;
    logic [7:0] packet [0:2055];
    integer cases=0, forwarded=0, dropped=0, errors=0;
    frame_filter dut(.*);
    control_regs regs(.*);

    task automatic base_packet(input logic [63:0] seq);
        for (integer n=0;n<2056;n=n+1) packet[n]=0;
        packet[0]=1;packet[2]='h5e;packet[3]='h4a;packet[4]='h7d;packet[5]='h20;
        packet[6]=2;packet[11]=1;
        packet[12]=8;packet[13]=0;
        packet[14]='h45;packet[17]=86;packet[22]=64;packet[23]=17;
        packet[26]=20;packet[27]=1;packet[28]=1;packet[29]=1;
        packet[30]=233;packet[31]=74;packet[32]=125;packet[33]=32;
        packet[34]='h9c;packet[35]='h40;packet[36]='h79;packet[37]='h38;
        packet[39]=66;
        for (integer n=0;n<10;n=n+1) packet[42+n]='h30+n;
        for (integer n=0;n<8;n=n+1) packet[52+n]=seq[(7-n)*8+:8];
        packet[61]=1;packet[63]=36;packet[64]='h41;
        packet[65]='h1f;packet[66]='h9f;
        packet[88]='h4e;packet[89]='h56;packet[90]='h44;packet[91]='h41;
        packet[92]='h20;packet[93]='h20;packet[94]='h20;packet[95]='h20;
    endtask

    task automatic control(input bit want_arm,input bit want_disarm);
        @(negedge clk);wr_en=1;wr_addr=1;wr_data={30'd0,want_disarm,want_arm};
        @(negedge clk);wr_en=0;
        @(negedge clk);
    endtask

    // outcome: 0=forward byte-for-byte, 1=policy drop, 2=error discard.
    task automatic exchange(input integer length,input integer outcome,
                            input bit bad_mac,input bit bad_keep,
                            input bit stall_tx,input bit gap_rx);
        integer pos, received, guard, beat, total;
        logic [63:0] held_data;
        logic [7:0] held_keep;
        logic held_last;
        for (pos=0;pos<length;pos=pos+8) begin
            @(negedge clk);
            while (!s_ready) @(negedge clk);
            s_data=0;s_keep=0;
            for (integer k=0;k<8;k=k+1)
                if (pos+k<length) begin s_data[k*8+:8]=packet[pos+k];s_keep[k]=1;end
            s_last=(pos+8>=length);s_error=s_last&&bad_mac;
            if (s_last&&bad_keep) s_keep=8'h05;
            s_valid=1;
            @(negedge clk);s_valid=0;s_last=0;s_error=0;
            if (gap_rx) repeat (2) @(negedge clk);
        end
        received=0;guard=0;
        if (stall_tx) m_ready=0;
        while (!m_valid && !s_ready && guard<20) begin @(negedge clk);guard=guard+1;end
        if (outcome==0) begin
            if (!m_valid) $fatal(1,"case %0d missing output",cases);
            if (stall_tx) begin
                held_data=m_data;held_keep=m_keep;held_last=m_last;
                repeat (4) begin
                    @(negedge clk);
                    if (!m_valid||m_data!==held_data||m_keep!==held_keep||m_last!==held_last)
                        $fatal(1,"backpressure stability");
                    if(s_ready) $fatal(1,"single buffer overwritten");
                end
                m_ready=1;
            end
            total=(length+7)/8;
            for (beat=0;beat<total;beat=beat+1) begin
                if (!m_valid) $fatal(1,"output interrupted");
                if (m_last !== (beat==total-1)) $fatal(1,"last mismatch");
                for (integer k=0;k<8;k=k+1) begin
                    if(m_keep[k] !== (received<length)) $fatal(1,"keep mismatch");
                    if(m_keep[k]) begin
                        if(m_data[k*8+:8]!==packet[received])
                            $fatal(1,"case %0d byte %0d changed",cases,received);
                        received=received+1;
                    end
                end
                @(negedge clk);
            end
            forwarded=forwarded+1;
        end else begin
            if(m_valid) $fatal(1,"case %0d discarded frame leaked, match=%b transport=%b message=%b bytes=%d header=%h",cases,dut.match_nvda,dut.matcher.transport_ok,dut.matcher.message_ok,dut.byte_count,dut.prefix);
            if(outcome==1) dropped=dropped+1;else errors=errors+1;
        end
        cases=cases+1;
        @(negedge clk);
        if(rx_count!==cases||tx_count!==forwarded||drop_count!==dropped||error_count!==errors)
            $fatal(1,"counter mismatch case %0d rx=%0d tx=%0d drop=%0d err=%0d",
                   cases,rx_count,tx_count,drop_count,error_count);
    endtask

    initial begin
        repeat(3) @(negedge clk);rst=0;
        base_packet(1);exchange(100,0,0,0,0,0); // Disarmed target passes.
        control(1,0);
        base_packet(2);packet[88]='h41;exchange(100,0,0,0,0,0);
        if(!armed) $fatal(1,"non-target consumed credit");
        base_packet(3);exchange(100,1,0,0,0,0);
        if(armed||last_sequence!=3) $fatal(1,"one-shot capture");
        base_packet(4);exchange(100,0,0,0,1,0);
        control(1,0);
        base_packet(5);packet[64]='h44;exchange(100,0,0,0,0,0);
        base_packet(6);packet[66]=0;exchange(100,0,0,0,0,0);
        base_packet(7);packet[95]=0;exchange(100,0,0,0,0,0);
        base_packet(8);packet[37]='h39;exchange(100,0,0,0,0,0);
        base_packet(9);packet[33]=33;exchange(100,0,0,0,0,0);
        base_packet(10);packet[29]=2;exchange(100,0,0,0,0,0);
        base_packet(11);packet[20]='h20;exchange(100,0,0,0,0,0);
        base_packet(12);packet[14]='h46;exchange(100,0,0,0,0,0);
        base_packet(13);packet[12]='h81;exchange(100,0,0,0,0,0);
        base_packet(14);packet[61]=2;exchange(100,0,0,0,0,0);
        base_packet(15);packet[63]=35;exchange(100,0,0,0,0,0);
        base_packet(16);exchange(99,0,0,0,0,0);
        base_packet(17);exchange(100,2,1,0,0,0);
        base_packet(18);exchange(100,2,0,1,0,0);
        base_packet(19);exchange(2048,0,0,0,1,0);
        base_packet(20);exchange(2049,2,0,0,0,0);
        if(!armed) $fatal(1,"error/unsupported frame consumed credit");
        base_packet(64'h12345678fedcba98);exchange(100,1,0,0,0,1);
        if(last_sequence!=64'h12345678fedcba98) $fatal(1,"sequence not latched");
        control(1,0);control(0,1);
        base_packet(22);exchange(100,0,0,0,0,0);
        control(1,1);
        if(armed) $fatal(1,"disarm must win over arm");
        rd_addr=0;#1;if(rd_data!=32'h464c4c45) $fatal(1,"app ID register");
        rd_addr=1;#1;if(rd_data!=0) $fatal(1,"command must not latch");
        rd_addr=2;#1;if(rd_data!=0) $fatal(1,"armed readback");
        rd_addr=5;#1;if(rd_data!=2) $fatal(1,"drop counter register");
        rd_addr=7;#1;if(rd_data!=32'h12345678) $fatal(1,"sequence high register");
        rd_addr=8;#1;if(rd_data!=32'hfedcba98) $fatal(1,"sequence low register");
        $display("cases=%0d forwarded=%0d policy_drop=%0d error_discard=%0d",cases,forwarded,dropped,errors);
        $display("byte_preservation=PASS one_shot=PASS backpressure=PASS registers=PASS");
        $display("functional_simulation=PASS hardware_implementation=NOT_RUN");
        $finish;
    end
    initial begin #200000;$fatal(1,"simulation timeout");end
endmodule
