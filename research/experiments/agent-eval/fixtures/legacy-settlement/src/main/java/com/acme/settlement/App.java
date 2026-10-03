package com.acme.settlement;

public class App {
    public static void main(String[] args) {
        SettlementService service = new SettlementService();
        System.out.println("settled: " + service.settle("batch-001"));
    }
}
