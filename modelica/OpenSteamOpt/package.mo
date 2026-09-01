within ;
package OpenSteamOpt
  "Independent educational steam-and-power grey-box models"

  model TwoBoilerSteamPlant
    "Two non-identical boilers, HP/MP inventories, back-pressure turbine and PRV"
    Modelica.Blocks.Interfaces.RealInput boiler1Setpoint(unit="t/h");
    Modelica.Blocks.Interfaces.RealInput boiler2Setpoint(unit="t/h");
    Modelica.Blocks.Interfaces.RealInput turbineSetpoint(unit="t/h");
    Modelica.Blocks.Interfaces.RealInput prvSetpoint(unit="t/h");
    Modelica.Blocks.Interfaces.RealInput hpDemand(unit="t/h");
    Modelica.Blocks.Interfaces.RealInput mpDemand(unit="t/h");

    Modelica.Blocks.Interfaces.RealOutput boiler1Flow(unit="t/h");
    Modelica.Blocks.Interfaces.RealOutput boiler2Flow(unit="t/h");
    Modelica.Blocks.Interfaces.RealOutput boiler1Fuel(unit="MW");
    Modelica.Blocks.Interfaces.RealOutput boiler2Fuel(unit="MW");
    Modelica.Blocks.Interfaces.RealOutput turbineFlow(unit="t/h");
    Modelica.Blocks.Interfaces.RealOutput prvFlow(unit="t/h");
    Modelica.Blocks.Interfaces.RealOutput turbinePower(unit="MW");
    Modelica.Blocks.Interfaces.RealOutput hpPressure(unit="bar");
    Modelica.Blocks.Interfaces.RealOutput mpPressure(unit="bar");

    parameter Real boiler1Max(unit="t/h") = 80;
    parameter Real boiler2Max(unit="t/h") = 60;
    parameter Real boiler1Tau(unit="s") = 90;
    parameter Real boiler2Tau(unit="s") = 150;
    parameter Real turbineTau(unit="s") = 45;
    parameter Real prvTau(unit="s") = 12;
    parameter Real boiler1Ramp(unit="t/h/s") = 28/3600;
    parameter Real boiler2Ramp(unit="t/h/s") = 18/3600;
    parameter Real turbineRamp(unit="t/h/s") = 30/3600;
    parameter Real prvRamp(unit="t/h/s") = 280/3600;
    parameter Real hpNominal(unit="bar") = 50;
    parameter Real mpNominal(unit="bar") = 10;
    parameter Real hpGain(unit="bar/t") = 0.08;
    parameter Real mpGain(unit="bar/t") = 0.12;
    parameter Real pressureTrim(unit="t/h/bar") = 2;
    parameter Real steamEnergy(unit="MWh/t") = 0.75;
    parameter Real turbineCoefficient(unit="MW/(t/h)") = 0.12;

  protected
    Real boiler1Command(unit="t/h");
    Real boiler2Command(unit="t/h");
    Real boiler1Efficiency;
    Real boiler2Efficiency;
    Real b1Load;
    Real b2Load;
    Real hpResidual(unit="t/h");
    Real mpResidual(unit="t/h");

  initial equation
    boiler1Flow = 50;
    boiler2Flow = 25;
    turbineFlow = 25;
    prvFlow = 15;
    hpPressure = hpNominal;
    mpPressure = mpNominal;

  equation
    boiler1Command = min(boiler1Max, max(0, boiler1Setpoint + 0.6*pressureTrim*(hpNominal - hpPressure)));
    boiler2Command = min(boiler2Max, max(0, boiler2Setpoint + 0.4*pressureTrim*(hpNominal - hpPressure)));
    der(boiler1Flow) = min(boiler1Ramp, max(-boiler1Ramp, (boiler1Command - boiler1Flow)/boiler1Tau));
    der(boiler2Flow) = min(boiler2Ramp, max(-boiler2Ramp, (boiler2Command - boiler2Flow)/boiler2Tau));
    der(turbineFlow) = min(turbineRamp, max(-turbineRamp, (turbineSetpoint - turbineFlow)/turbineTau));
    der(prvFlow) = min(prvRamp, max(-prvRamp, (prvSetpoint - prvFlow)/prvTau));

    b1Load = min(1, max(0, boiler1Flow/boiler1Max));
    b2Load = min(1, max(0, boiler2Flow/boiler2Max));
    boiler1Efficiency = max(0.75, 0.80 + 0.18*b1Load - 0.11*b1Load*b1Load);
    boiler2Efficiency = max(0.65, 0.69 + 0.18*b2Load - 0.09*b2Load*b2Load);
    boiler1Fuel = steamEnergy*boiler1Flow/boiler1Efficiency;
    boiler2Fuel = steamEnergy*boiler2Flow/boiler2Efficiency;
    turbinePower = turbineCoefficient*turbineFlow;

    hpResidual = boiler1Flow + boiler2Flow - hpDemand - turbineFlow - prvFlow;
    mpResidual = turbineFlow + prvFlow - mpDemand;
    der(hpPressure) = hpGain*hpResidual/3600;
    der(mpPressure) = mpGain*mpResidual/3600;

    annotation(experiment(StartTime=0, StopTime=86400, Interval=60, Tolerance=1e-6));
  end TwoBoilerSteamPlant;

end OpenSteamOpt;
